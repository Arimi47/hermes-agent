"""
Create a Note or Task and link it to a person/deal/lead/company via target table.

Usage:
    # Note
    python3 add_note_task.py --kind note \
        --attach-to-type person --attach-to-id <uuid> \
        --title "..." --body "markdown body"

    # Task
    python3 add_note_task.py --kind task \
        --attach-to-type deal --attach-to-id <uuid> \
        --title "Scope-Entwurf senden" [--body "..."] \
        [--due 2026-05-01] [--status TODO|IN_PROGRESS|DONE]
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from tw_api import api, extract_created_id, success, fail  # noqa: E402

TARGET_TYPE_TO_FIELD = {
    "person": "personId",
    "deal": "opportunityId",
    "lead": "leadId",
    "company": "companyId",
}
TASK_STATUS = {"TODO", "IN_PROGRESS", "DONE"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=["note", "task"])
    ap.add_argument("--attach-to-type", required=True,
                    choices=sorted(TARGET_TYPE_TO_FIELD))
    ap.add_argument("--attach-to-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--body", default=None)
    ap.add_argument("--due", default=None, help="YYYY-MM-DD (tasks only)")
    ap.add_argument("--status", default="TODO", choices=sorted(TASK_STATUS))
    args = ap.parse_args()

    target_field = TARGET_TYPE_TO_FIELD[args.attach_to_type]

    if args.kind == "note":
        payload = {"title": args.title}
        if args.body:
            payload["body"] = {"markdown": args.body}
        code, resp = api("POST", "/rest/notes", payload)
        if code >= 300:
            fail(f"Note create failed {code}", resp)
            return
        nid = extract_created_id(resp) if isinstance(resp, dict) else None
        if not nid:
            fail("Note created but no id returned", resp)
            return
        # Link via noteTarget
        link_payload = {"noteId": nid, target_field: args.attach_to_id}
        lc, lresp = api("POST", "/rest/noteTargets", link_payload)
        if lc >= 300:
            fail(f"noteTarget link failed {lc}", lresp)
            return
        success({"kind": "note", "id": nid, "linked": args.attach_to_type})
    else:  # task
        payload = {"title": args.title, "status": args.status}
        if args.body:
            payload["body"] = {"markdown": args.body}
        if args.due:
            payload["dueAt"] = f"{args.due}T09:00:00.000Z"
        code, resp = api("POST", "/rest/tasks", payload)
        if code >= 300:
            fail(f"Task create failed {code}", resp)
            return
        tid = extract_created_id(resp) if isinstance(resp, dict) else None
        if not tid:
            fail("Task created but no id returned", resp)
            return
        link_payload = {"taskId": tid, target_field: args.attach_to_id}
        lc, lresp = api("POST", "/rest/taskTargets", link_payload)
        if lc >= 300:
            fail(f"taskTarget link failed {lc}", lresp)
            return
        success({"kind": "task", "id": tid, "linked": args.attach_to_type, "due": args.due})


if __name__ == "__main__":
    main()
