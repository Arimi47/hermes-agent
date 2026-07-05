"""MS365 token-freshness probe.

Refresh tokens sterben nach ~90 Tagen Inaktivitaet - ohne Probe faellt
das erst auf, wenn Ari eine Mail braucht (der MCP-Server refresht nur
on-demand). Dieser Probe-Loop (stuendlich via start.sh) macht pro
Mailbox einen silent refresh + GET /me und schreibt das Ergebnis nach
$HERMES_HOME/ms365-probe-status.json. Ein Fehlschlag landet als laute
Warnung im Gateway-Log, Tage bevor der Token wirklich gebraucht wird.

Nebeneffekt (gewollt): der regelmaessige silent refresh haelt die
Refresh-Tokens aktiv und persistiert rotierte Tokens zurueck in die
Cache-Datei (atomar; der MCP-Server laedt sie per mtime-Check neu).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from msal import ConfidentialClientApplication, PublicClientApplication, SerializableTokenCache

# Railway injects MS365_MCP_*; the MCP server sees MS365_* via config.seed
# env mapping. The probe runs from start.sh (Railway env), so accept both.
CLIENT_ID = os.environ.get("MS365_CLIENT_ID") or os.environ.get("MS365_MCP_CLIENT_ID")
TENANT_ID = os.environ.get("MS365_TENANT_ID") or os.environ.get("MS365_MCP_TENANT_ID")
CLIENT_SECRET = os.environ.get("MS365_CLIENT_SECRET") or os.environ.get("MS365_MCP_CLIENT_SECRET")
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "/data/.hermes"))
STATUS_FILE = HERMES_HOME / "ms365-probe-status.json"

# Keep in sync with server.py MAILBOXES.
MAILBOXES: dict[str, Path] = {
    "abirnbaum": HERMES_HOME / "ms365_tokens.json",
    "instandhaltung": HERMES_HOME / "ms365_tokens_instandhaltung.json",
    "lohn": HERMES_HOME / "ms365_tokens_lohn.json",
}
SCOPES = [
    "Mail.Read", "Mail.Send", "Mail.Read.Shared", "Mail.Send.Shared",
    "User.Read", "User.ReadBasic.All",
]


def probe_mailbox(mailbox: str, path: Path) -> dict:
    if not path.exists():
        return {"ok": False, "error": f"token file missing: {path}"}
    cache = SerializableTokenCache()
    cache.deserialize(path.read_text(encoding="utf-8"))
    if CLIENT_SECRET:
        app = ConfidentialClientApplication(
            client_id=CLIENT_ID, client_credential=CLIENT_SECRET,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            token_cache=cache)
    else:
        app = PublicClientApplication(
            client_id=CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
            token_cache=cache)
    accounts = app.get_accounts()
    if not accounts:
        return {"ok": False, "error": "token cache empty (re-run ms365_login.py)"}
    result = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
    if not result or "access_token" not in result:
        detail = (result or {}).get("error_description") or repr(result)
        return {"ok": False, "error": f"silent refresh failed: {detail[:250]}"}
    r = httpx.get(
        "https://graph.microsoft.com/v1.0/me",
        headers={"Authorization": f"Bearer {result['access_token']}"},
        timeout=30.0,
    )
    if r.status_code != 200:
        return {"ok": False, "error": f"GET /me -> {r.status_code}: {r.text[:200]}"}
    if cache.has_state_changed:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(cache.serialize(), encoding="utf-8")
        os.replace(tmp, path)
    return {"ok": True, "user": r.json().get("userPrincipalName")}


def main() -> None:
    if not CLIENT_ID or not TENANT_ID:
        print("[probe] MS365 client/tenant env not set - skipping", file=sys.stderr)
        return
    results: dict[str, dict] = {}
    for mailbox, path in MAILBOXES.items():
        try:
            results[mailbox] = probe_mailbox(mailbox, path)
        except Exception as e:
            results[mailbox] = {"ok": False, "error": str(e)[:250]}
    payload = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mailboxes": results,
    }
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS_FILE.with_name(STATUS_FILE.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, STATUS_FILE)
    for mailbox, res in results.items():
        if res.get("ok"):
            print(f"[probe] {mailbox}: OK ({res.get('user')})")
        else:
            print(f"[probe] WARNUNG {mailbox}: {res.get('error')}", file=sys.stderr)


if __name__ == "__main__":
    main()
