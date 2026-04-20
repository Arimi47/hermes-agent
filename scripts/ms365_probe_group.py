"""Probe if instandhaltung is a M365 group / distribution list."""
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
tok = app.acquire_token_silent(
    scopes=["User.ReadBasic.All"], account=app.get_accounts()[0]
)
H = {"Authorization": f"Bearer {tok['access_token']}"}

print("=== group lookup ===")
r = httpx.get(
    "https://graph.microsoft.com/v1.0/groups",
    headers=H,
    params={
        "$filter": "mail eq 'instandhaltung@buero-birnbaum.de'",
        "$select": "id,displayName,mail,mailEnabled,securityEnabled,groupTypes",
    },
    timeout=20.0,
)
print(f"HTTP {r.status_code}")
print(json.dumps(r.json(), indent=2)[:1500])

print("\n=== user details (with ...EmailAddresses proxy check) ===")
r2 = httpx.get(
    "https://graph.microsoft.com/v1.0/users/f4fbd367-b646-476f-b6d5-a1c5ed5dc89b",
    headers=H,
    params={
        "$select": "id,userPrincipalName,mail,mailNickname,proxyAddresses,assignedLicenses,showInAddressList,displayName",
    },
    timeout=20.0,
)
print(f"HTTP {r2.status_code}")
print(json.dumps(r2.json(), indent=2)[:1500])
