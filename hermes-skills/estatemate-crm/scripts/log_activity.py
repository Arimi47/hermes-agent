"""
Log an Activity to a Deal or Lead.

Constraint: exactly one of --parent-type deal|lead must be set.

Usage:
    python3 log_activity.py --parent-type deal --parent-id <uuid> \
        --typ TYPE_CALL --richtung DIR_OUTBOUND \
        --summary "Demo gezeigt, Patrick will abstimmen" \
        [--datum 2026-04-22T14:30:00Z] [--sentiment SENT_POSITIV]

Returns JSON with created activity id.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import api, extract_created_id, success, fail  # noqa: E402

VALID_TYP = {"TYPE_CALL", "TYPE_MEETING", "TYPE_DEMO", "TYPE_EMAIL", "TYPE_VOICE", "TYPE_SONSTIGES"}
VALID_RICHTUNG = {"DIR_OUTBOUND", "DIR_INBOUND"}
VALID_SENTIMENT = {"SENT_POSITIV", "SENT_NEUTRAL", "SENT_NEGATIV"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent-type", required=True, choices=["deal", "lead"])
    ap.add_argument("--parent-id", required=True)
    ap.add_argument("--typ", required=True, choices=sorted(VALID_TYP))
    ap.add_argument("--richtung", required=True, choices=sorted(VALID_RICHTUNG))
    ap.add_argument("--summary", required=True)
    ap.add_argument("--datum", default=None,
                    help="ISO-8601 UTC, default: now")
    ap.add_argument("--sentiment", default=None, choices=sorted(VALID_SENTIMENT))
    ap.add_argument("--name", default=None,
                    help="Short name for the Activity, default derived from typ+date")
    args = ap.parse_args()

    datum = args.datum or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    name = args.name or f"{args.typ.removeprefix('TYPE_').title()} {datum[:10]}"

    payload: dict = {
        "name": name,
        "aktivitaetDatum": datum,
        "typ": args.typ,
        "richtung": args.richtung,
        "summary": {"markdown": args.summary},
    }
    if args.sentiment:
        payload["sentiment"] = args.sentiment
    if args.parent_type == "deal":
        payload["dealId"] = args.parent_id
    else:
        payload["leadId"] = args.parent_id

    code, resp = api("POST", "/rest/activities", payload)
    if code >= 300:
        fail(f"POST failed {code}", resp)
        return
    aid = extract_created_id(resp) if isinstance(resp, dict) else None
    success({"activityId": aid, "name": name, "parentType": args.parent_type, "parentId": args.parent_id})


if __name__ == "__main__":
    main()
