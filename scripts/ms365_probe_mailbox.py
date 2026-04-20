"""Probe a mailbox via multiple Graph access paths, report which works."""
from __future__ import annotations

import json
import sys
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
tok = app.acquire_token_silent(scopes=["Mail.Read.Shared"], account=app.get_accounts()[0])
if cache.has_state_changed:
    cache_file.write_text(cache.serialize(), encoding="utf-8")
H = {"Authorization": f"Bearer {tok['access_token']}"}

for label, path in [
    ("lowercase UPN", "/users/instandhaltung@buero-birnbaum.de/mailFolders/inbox/messages"),
    ("exact UPN (big I)", "/users/Instandhaltung@buero-birnbaum.de/mailFolders/inbox/messages"),
    ("object id", "/users/f4fbd367-b646-476f-b6d5-a1c5ed5dc89b/mailFolders/inbox/messages"),
]:
    r = httpx.get(
        f"https://graph.microsoft.com/v1.0{path}",
        headers=H,
        params={"$top": 3, "$select": "subject,from,receivedDateTime"},
        timeout=20.0,
    )
    print(f"\n=== {label} -> HTTP {r.status_code} ===")
    if r.status_code == 200:
        for m in r.json().get("value", []):
            frm = (m.get("from") or {}).get("emailAddress") or {}
            print(f"  {m.get('receivedDateTime')} | {frm.get('address')} | {m.get('subject')}")
    else:
        print(json.dumps(r.json(), indent=2)[:600])
