"""Diagnostic: resolve the actual Graph user object for an SMTP address.

Run locally after ms365_login.py has produced a token cache. Prints
the UPN, id, mail, and proxyAddresses so we know exactly how Graph
sees the mailbox.

    python scripts/ms365_resolve.py instandhaltung@buero-birnbaum.de
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from msal import ConfidentialClientApplication, SerializableTokenCache

CRED = Path(
    "C:/Users/aribi/OneDrive/Desktop/chaim-private-credentials/"
    ".hermes_m365_credentials.json"
)
SCOPES = ["User.Read", "User.ReadBasic.All", "Mail.Read", "Mail.Read.Shared"]


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/ms365_resolve.py <smtp-address>", file=sys.stderr)
        return 1
    target = sys.argv[1]

    creds = json.loads(CRED.read_text(encoding="utf-8"))
    cache = SerializableTokenCache()
    cache_file = Path("ms365_tokens.json")
    if cache_file.exists():
        cache.deserialize(cache_file.read_text(encoding="utf-8"))

    app = ConfidentialClientApplication(
        client_id=creds["client_id"],
        client_credential=creds["client_secret"],
        authority=f"https://login.microsoftonline.com/{creds['tenant_id']}",
        token_cache=cache,
    )
    accounts = app.get_accounts()
    if not accounts:
        print("ERROR: no cached account - run ms365_login.py first", file=sys.stderr)
        return 2
    tok = app.acquire_token_silent(scopes=SCOPES, account=accounts[0])
    if not tok or "access_token" not in tok:
        print(f"ERROR: silent refresh failed: {tok}", file=sys.stderr)
        return 3
    if cache.has_state_changed:
        cache_file.write_text(cache.serialize(), encoding="utf-8")

    headers = {"Authorization": f"Bearer {tok['access_token']}"}

    print(f"--- lookup: /users?$filter=mail eq '{target}' ---")
    r = httpx.get(
        "https://graph.microsoft.com/v1.0/users",
        headers=headers,
        params={
            "$filter": f"mail eq '{target}'",
            "$select": "id,userPrincipalName,mail,displayName,mailNickname,proxyAddresses,accountEnabled",
        },
        timeout=20.0,
    )
    print(f"HTTP {r.status_code}")
    print(json.dumps(r.json(), indent=2))

    print(f"\n--- lookup: /users?$filter=proxyAddresses/any(p:p eq 'smtp:{target}') ---")
    r2 = httpx.get(
        "https://graph.microsoft.com/v1.0/users",
        headers=headers,
        params={
            "$filter": f"proxyAddresses/any(p:p eq 'smtp:{target}')",
            "$select": "id,userPrincipalName,mail,displayName,mailNickname,proxyAddresses,accountEnabled",
        },
        timeout=20.0,
    )
    print(f"HTTP {r2.status_code}")
    print(json.dumps(r2.json(), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
