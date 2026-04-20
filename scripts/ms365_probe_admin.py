"""Probe what the currently-cached token can see across target mailboxes."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
from msal import ConfidentialClientApplication, SerializableTokenCache

CRED = Path(
    "C:/Users/aribi/OneDrive/Desktop/chaim-private-credentials/"
    ".hermes_m365_credentials.json"
)
creds = json.loads(CRED.read_text(encoding="utf-8"))
cache = SerializableTokenCache()
cache_file = Path("ms365_tokens.json")
cache.deserialize(cache_file.read_text(encoding="utf-8"))
app = ConfidentialClientApplication(
    client_id=creds["client_id"],
    client_credential=creds["client_secret"],
    authority=f"https://login.microsoftonline.com/{creds['tenant_id']}",
    token_cache=cache,
)
account = app.get_accounts()[0]
print(f"Signed-in user: {account.get('username')!r}")
tok = app.acquire_token_silent(scopes=["Mail.Read.Shared", "User.ReadBasic.All"], account=account)
if cache.has_state_changed:
    cache_file.write_text(cache.serialize(), encoding="utf-8")
H = {"Authorization": f"Bearer {tok['access_token']}"}


def probe(label, url):
    r = httpx.get(url, headers=H, params={"$top": 2, "$select": "subject,from,receivedDateTime"}, timeout=20.0)
    print(f"\n=== {label} -> HTTP {r.status_code} ===")
    if r.status_code == 200:
        for m in r.json().get("value", []):
            frm = (m.get("from") or {}).get("emailAddress") or {}
            print(f"  {m.get('receivedDateTime')} | {frm.get('address')} | {m.get('subject')}")
    else:
        body = r.json()
        err = body.get("error", {})
        print(f"  {err.get('code')}: {err.get('message', '')[:200]}")


B = "https://graph.microsoft.com/v1.0"
probe("/me (admin's own inbox)", f"{B}/me/mailFolders/inbox/messages")
probe("/users/abirnbaum@buero-birnbaum.de", f"{B}/users/abirnbaum@buero-birnbaum.de/mailFolders/inbox/messages")
probe("/users/Instandhaltung@buero-birnbaum.de", f"{B}/users/Instandhaltung@buero-birnbaum.de/mailFolders/inbox/messages")
