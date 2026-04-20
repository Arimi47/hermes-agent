"""Verify the instandhaltung token cache points at Instandhaltung and
can read its own inbox. Run locally after ms365_login.py --mailbox
instandhaltung."""
from __future__ import annotations

import json
from pathlib import Path

import httpx
from msal import ConfidentialClientApplication, SerializableTokenCache

CRED = Path("C:/Users/aribi/OneDrive/Desktop/chaim-private-credentials/.hermes_m365_credentials.json")
CACHE = Path("ms365_tokens_instandhaltung.json")

creds = json.loads(CRED.read_text(encoding="utf-8"))
cache = SerializableTokenCache()
cache.deserialize(CACHE.read_text(encoding="utf-8"))
app = ConfidentialClientApplication(
    client_id=creds["client_id"],
    client_credential=creds["client_secret"],
    authority=f"https://login.microsoftonline.com/{creds['tenant_id']}",
    token_cache=cache,
)
account = app.get_accounts()[0]
print(f"Signed-in user: {account.get('username')!r}")

tok = app.acquire_token_silent(scopes=["Mail.Read"], account=account)
H = {"Authorization": f"Bearer {tok['access_token']}"}

r = httpx.get(
    "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages",
    headers=H,
    params={"$top": 5, "$select": "subject,from,receivedDateTime"},
    timeout=20.0,
)
print(f"/me/mailFolders/inbox/messages -> HTTP {r.status_code}")
if r.status_code == 200:
    for m in r.json().get("value", []):
        frm = (m.get("from") or {}).get("emailAddress") or {}
        subj = (m.get("subject") or "").encode("ascii", "replace").decode()
        print(f"  {m.get('receivedDateTime')} | {frm.get('address')} | {subj[:100]}")
else:
    print(json.dumps(r.json(), indent=2)[:600])
