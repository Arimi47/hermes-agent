"""
Create a Contact (Person) with optional Company link and Referrer flag.

Usage:
    python3 create_contact.py --first "Klara" --last "Nowak" \
        [--company-id <uuid>] [--email a@b.de] [--phone "+491234"] \
        [--titel "Head of Real Estate"] [--buying-role ROLE_CHAMPION] \
        [--is-referrer false|true] [--sprache LANG_DE|LANG_EN]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import api, extract_created_id, success, fail  # noqa: E402

ROLES = {"ROLE_ECONOMIC_BUYER", "ROLE_CHAMPION", "ROLE_USER", "ROLE_NO_ROLE"}
LANGS = {"LANG_DE", "LANG_EN"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", required=True)
    ap.add_argument("--last", required=True)
    ap.add_argument("--company-id", default=None)
    ap.add_argument("--email", default=None)
    ap.add_argument("--phone", default=None)
    ap.add_argument("--titel", default=None)
    ap.add_argument("--buying-role", default=None, choices=sorted(ROLES))
    ap.add_argument("--is-referrer", default="false", choices=["true", "false"])
    ap.add_argument("--sprache", default=None, choices=sorted(LANGS))
    args = ap.parse_args()

    payload: dict = {
        "name": {"firstName": args.first, "lastName": args.last},
        "isReferrer": args.is_referrer == "true",
    }
    if args.company_id:
        payload["companyId"] = args.company_id
    if args.email:
        payload["emails"] = {"primaryEmail": args.email, "additionalEmails": []}
    if args.phone:
        payload["phones"] = {
            "primaryPhoneCountryCode": "DE",
            "primaryPhoneNumber": args.phone,
            "additionalPhones": [],
        }
    if args.titel:
        payload["titel"] = args.titel
    if args.buying_role:
        payload["buyingRole"] = args.buying_role
    if args.sprache:
        payload["sprache"] = args.sprache

    code, resp = api("POST", "/rest/people", payload)
    if code >= 300:
        fail(f"POST failed {code}", resp)
        return
    pid = extract_created_id(resp) if isinstance(resp, dict) else None
    success({
        "personId": pid,
        "firstName": args.first, "lastName": args.last,
        "isReferrer": payload["isReferrer"],
        "companyId": payload.get("companyId"),
    })


if __name__ == "__main__":
    main()
