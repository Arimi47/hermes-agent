"""
Update Deal or Lead stage. Automatically sets stageSeit to today (Deals only).

Usage:
    python3 update_stage.py --type deal --id <uuid> --stage STAGE_ANGEBOT
    python3 update_stage.py --type lead --id <uuid> --stage STAGE_QUALIFIZIERT

Deal stages: STAGE_GESPRAECH, STAGE_DEMO, STAGE_PILOT, STAGE_ANGEBOT, STAGE_WON, STAGE_LOST
Lead stages: STAGE_NEU, STAGE_KONTAKTIERT, STAGE_GEANTWORTET, STAGE_NURTURING, STAGE_QUALIFIZIERT, STAGE_DISQUALIFIZIERT
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import api, success, fail  # noqa: E402

DEAL_STAGES = {"STAGE_GESPRAECH", "STAGE_DEMO", "STAGE_PILOT", "STAGE_ANGEBOT", "STAGE_WON", "STAGE_LOST"}
LEAD_STAGES = {"STAGE_NEU", "STAGE_KONTAKTIERT", "STAGE_GEANTWORTET", "STAGE_NURTURING",
               "STAGE_QUALIFIZIERT", "STAGE_DISQUALIFIZIERT"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--type", required=True, choices=["deal", "lead"])
    ap.add_argument("--id", required=True)
    ap.add_argument("--stage", required=True)
    args = ap.parse_args()

    today = dt.date.today().isoformat()
    if args.type == "deal":
        if args.stage not in DEAL_STAGES:
            fail(f"Invalid deal stage. Allowed: {sorted(DEAL_STAGES)}")
            return
        payload = {"stage": args.stage, "stageSeit": today}
        path = f"/rest/opportunities/{args.id}"
    else:
        if args.stage not in LEAD_STAGES:
            fail(f"Invalid lead stage. Allowed: {sorted(LEAD_STAGES)}")
            return
        payload = {"stage": args.stage}  # Lead has no stageSeit in schema
        path = f"/rest/leads/{args.id}"

    code, resp = api("PATCH", path, payload)
    if code >= 300:
        fail(f"PATCH failed {code}", resp)
        return
    success({"id": args.id, "type": args.type, "newStage": args.stage,
             "stageSeit": today if args.type == "deal" else None})


if __name__ == "__main__":
    main()
