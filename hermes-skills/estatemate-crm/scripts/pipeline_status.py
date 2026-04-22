"""
Pipeline overview: active deals, open leads, next actions due, stale referrers.

Usage:
    python3 pipeline_status.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import list_all, success  # noqa: E402


def main() -> None:
    today = dt.date.today()

    deals = list_all("opportunities", "opportunities", limit=100)
    leads = list_all("leads", "leads", limit=100)
    people = list_all("people", "people", limit=100)

    active_deal_stages = {"STAGE_GESPRAECH", "STAGE_DEMO", "STAGE_PILOT", "STAGE_ANGEBOT"}
    active_deals = [d for d in deals if d.get("stage") in active_deal_stages]
    won_deals = [d for d in deals if d.get("stage") == "STAGE_WON"]
    lost_deals = [d for d in deals if d.get("stage") == "STAGE_LOST"]

    deals_aging = []
    for d in active_deals:
        seit = d.get("stageSeit")
        if seit:
            try:
                days = (today - dt.date.fromisoformat(seit)).days
                if days > 14:
                    deals_aging.append({"id": d["id"], "name": d.get("name"),
                                        "stage": d.get("stage"), "daysInStage": days})
            except Exception:
                pass

    open_leads = [l for l in leads if l.get("stage") in
                  {"STAGE_NEU", "STAGE_KONTAKTIERT", "STAGE_GEANTWORTET", "STAGE_NURTURING"}]

    next_actions_due = []
    for r in active_deals + open_leads:
        nab = r.get("nextActionBis")
        if nab:
            try:
                due = dt.date.fromisoformat(nab)
                if due <= today:
                    next_actions_due.append({
                        "id": r["id"], "name": r.get("name"),
                        "nextAction": r.get("nextAction"),
                        "dueDate": nab,
                        "type": "deal" if r in active_deals else "lead",
                    })
            except Exception:
                pass

    referrers = [p for p in people if p.get("isReferrer")]

    payload = {
        "date": today.isoformat(),
        "deals": {
            "active": len(active_deals),
            "won": len(won_deals),
            "lost": len(lost_deals),
            "aging_over_14d": deals_aging,
        },
        "leads": {
            "open": len(open_leads),
            "byStage": {
                s: sum(1 for l in leads if l.get("stage") == s)
                for s in ["STAGE_NEU", "STAGE_KONTAKTIERT", "STAGE_GEANTWORTET",
                          "STAGE_NURTURING", "STAGE_QUALIFIZIERT", "STAGE_DISQUALIFIZIERT"]
            },
        },
        "next_actions_due": next_actions_due,
        "referrers": {
            "total": len(referrers),
            "names": [
                {"id": p["id"], "name": f"{(p.get('name') or {}).get('firstName','')} "
                                         f"{(p.get('name') or {}).get('lastName','')}".strip()}
                for p in referrers
            ],
        },
    }
    success(payload)


if __name__ == "__main__":
    main()
