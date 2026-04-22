"""
Create a new Lead. Validates that referrer (if given) has isReferrer=true.

Usage:
    python3 create_lead.py --name "..." --company-text "..." \
        [--person-id <uuid>] [--referrer-id <uuid>] \
        [--source SRC_NETWORK|SRC_REFERRAL|SRC_INBOUND|SRC_EVENT|SRC_SONSTIGES] \
        [--stage STAGE_NEU] [--icp-quick-fit SCORE_3] \
        [--next-action "..."] [--next-action-bis 2026-05-01] \
        [--notes "markdown notes"]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import api, extract_created_id, success, fail  # noqa: E402

SOURCES = {"SRC_NETWORK", "SRC_REFERRAL", "SRC_INBOUND", "SRC_EVENT", "SRC_SONSTIGES"}
STAGES = {"STAGE_NEU", "STAGE_KONTAKTIERT", "STAGE_GEANTWORTET", "STAGE_NURTURING",
          "STAGE_QUALIFIZIERT", "STAGE_DISQUALIFIZIERT"}
SCORES = {"SCORE_1", "SCORE_2", "SCORE_3", "SCORE_4", "SCORE_5"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--company-text", default=None)
    ap.add_argument("--person-id", default=None)
    ap.add_argument("--referrer-id", default=None)
    ap.add_argument("--source", default="SRC_NETWORK", choices=sorted(SOURCES))
    ap.add_argument("--stage", default="STAGE_NEU", choices=sorted(STAGES))
    ap.add_argument("--icp-quick-fit", default=None, choices=sorted(SCORES))
    ap.add_argument("--next-action", default=None)
    ap.add_argument("--next-action-bis", default=None, help="YYYY-MM-DD")
    ap.add_argument("--notes", default=None, help="Markdown text")
    args = ap.parse_args()

    # Validate referrer has isReferrer=true
    if args.referrer_id:
        code, resp = api("GET", f"/rest/people/{args.referrer_id}")
        if code >= 300 or not isinstance(resp, dict):
            fail(f"Referrer lookup failed: {code}", resp)
            return
        person = resp.get("data", {}).get("person", {})
        if not person.get("isReferrer"):
            fail(f"Referrer person {args.referrer_id} does not have isReferrer=true. "
                 f"Set it first via update or choose another person.")
            return

    payload: dict = {
        "name": args.name,
        "leadSource": args.source,
        "stage": args.stage,
    }
    if args.company_text:
        payload["companyText"] = args.company_text
    if args.person_id:
        payload["personId"] = args.person_id
    if args.referrer_id:
        payload["referrerId"] = args.referrer_id
    if args.icp_quick_fit:
        payload["icpQuickFit"] = args.icp_quick_fit
    if args.next_action:
        payload["nextAction"] = args.next_action
    if args.next_action_bis:
        payload["nextActionBis"] = args.next_action_bis
    if args.notes:
        payload["notes"] = {"markdown": args.notes}

    code, resp = api("POST", "/rest/leads", payload)
    if code >= 300:
        fail(f"POST failed {code}", resp)
        return
    lid = extract_created_id(resp) if isinstance(resp, dict) else None
    success({"leadId": lid, "name": args.name, "stage": args.stage})


if __name__ == "__main__":
    main()
