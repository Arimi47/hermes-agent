"""
Search Twenty records by name.

Usage:
    python3 search.py --type person|company|deal|lead --query "<substring>"

Returns JSON with matches.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import find_by_name, find_person_by_name, success, fail  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=["person", "company", "deal", "lead"])
    ap.add_argument("--query", required=True)
    args = ap.parse_args()

    if args.type == "person":
        matches = find_person_by_name(args.query)
        results = []
        for p in matches:
            n = p.get("name", {}) or {}
            results.append({
                "id": p["id"],
                "firstName": n.get("firstName"),
                "lastName": n.get("lastName"),
                "companyId": p.get("companyId"),
                "isReferrer": p.get("isReferrer"),
                "titel": p.get("titel"),
                "buyingRole": p.get("buyingRole"),
            })
    elif args.type == "company":
        matches = find_by_name("companies", "companies", args.query)
        results = [{
            "id": c["id"], "name": c.get("name"),
            "companyType": c.get("companyType"),
            "wohneinheiten": c.get("wohneinheiten"),
            "gewerbeeinheiten": c.get("gewerbeeinheiten"),
            "icpScore": c.get("icpScore"),
            "employees": c.get("employees"),
        } for c in matches]
    elif args.type == "deal":
        matches = find_by_name("opportunities", "opportunities", args.query)
        results = [{
            "id": o["id"], "name": o.get("name"),
            "stage": o.get("stage"), "stageSeit": o.get("stageSeit"),
            "companyId": o.get("companyId"),
            "pointOfContactId": o.get("pointOfContactId"),
            "probability": o.get("probability"),
            "nextAction": o.get("nextAction"),
            "nextActionBis": o.get("nextActionBis"),
        } for o in matches]
    elif args.type == "lead":
        matches = find_by_name("leads", "leads", args.query)
        results = [{
            "id": l["id"], "name": l.get("name"),
            "stage": l.get("stage"),
            "companyText": l.get("companyText"),
            "personId": l.get("personId"),
            "referrerId": l.get("referrerId"),
            "leadSource": l.get("leadSource"),
            "nextAction": l.get("nextAction"),
            "nextActionBis": l.get("nextActionBis"),
        } for l in matches]
    else:
        fail(f"Unknown type: {args.type}")
        return

    success({"type": args.type, "count": len(results), "matches": results})


if __name__ == "__main__":
    main()
