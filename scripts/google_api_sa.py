#!/usr/bin/env python3
"""Service-account-backed Google Workspace CLI for Hermes (DWD impersonation).

Drop-in alongside the user-OAuth google_api.py skill. Reads:
  HERMES_HOME / google_service_account.json   - the SA private key
  HERMES_HOME / google_subject                - target user email (one line)

Falls back to env vars HERMES_SA_JSON, HERMES_GOOGLE_SUBJECT.

CLI shape mirrors the existing skill's google_api.py:
  gmail search QUERY [--max N]
  gmail get MESSAGE_ID
  gmail send --to EMAIL --subject S --body B [--cc EMAIL] [--bcc EMAIL]
  gmail draft --to EMAIL --subject S --body B
  gmail reply MESSAGE_ID --body B
  calendar list [--from ISO] [--to ISO] [--calendar primary] [--max N]
  calendar create --summary S --start ISO --end ISO [--description D]
                  [--location L] [--attendees a@b c@d] [--calendar primary]
                  [--tz Europe/Berlin]
  calendar list-calendars
  drive search QUERY [--max N]
  drive list [--folder FOLDER_ID] [--max N]
  whoami
  check
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build


SCOPES = (
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/documents",
)


def _hermes_home() -> Path:
    val = os.environ.get("HERMES_HOME", "").strip()
    return Path(val) if val else Path.home() / ".hermes"


def _sa_path() -> Path:
    env = os.environ.get("HERMES_SA_JSON")
    if env:
        return Path(env)
    return _hermes_home() / "google_service_account.json"


def _subject() -> str:
    env = os.environ.get("HERMES_GOOGLE_SUBJECT")
    if env:
        return env.strip()
    p = _hermes_home() / "google_subject"
    if p.exists():
        text = p.read_text(encoding="utf-8").strip()
        if text:
            return text
    raise SystemExit(
        f"No delegate user configured. Set HERMES_GOOGLE_SUBJECT or write the "
        f"target email to {p}"
    )


def _service(api: str, version: str):
    creds = service_account.Credentials.from_service_account_file(
        str(_sa_path()), scopes=list(SCOPES)
    ).with_subject(_subject())
    return build(api, version, credentials=creds, cache_discovery=False)


def _rfc3339(value: str | datetime) -> str:
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


# ----- gmail ---------------------------------------------------------------

def _gmail():
    return _service("gmail", "v1")


def gmail_search(query: str, max_results: int) -> None:
    res = _gmail().users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    msgs = res.get("messages", [])
    print(json.dumps({"query": query, "count": len(msgs), "ids": [m["id"] for m in msgs]}, indent=2))


def gmail_get(message_id: str) -> None:
    msg = _gmail().users().messages().get(userId="me", id=message_id, format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    print(json.dumps({
        "id": msg["id"],
        "threadId": msg["threadId"],
        "labels": msg.get("labelIds", []),
        "from": headers.get("From"),
        "to": headers.get("To"),
        "subject": headers.get("Subject"),
        "date": headers.get("Date"),
        "snippet": msg.get("snippet"),
    }, indent=2))


def _build_mime(to: str, subject: str, body: str,
                cc: str | None = None, bcc: str | None = None) -> str:
    msg = EmailMessage()
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def gmail_send(to: str, subject: str, body: str,
               cc: str | None, bcc: str | None) -> None:
    raw = _build_mime(to, subject, body, cc, bcc)
    out = _gmail().users().messages().send(userId="me", body={"raw": raw}).execute()
    print(json.dumps({"sent_id": out["id"], "thread_id": out.get("threadId")}, indent=2))


def gmail_draft(to: str, subject: str, body: str) -> None:
    raw = _build_mime(to, subject, body)
    out = _gmail().users().drafts().create(
        userId="me", body={"message": {"raw": raw}}
    ).execute()
    print(json.dumps({"draft_id": out["id"]}, indent=2))


def gmail_reply(message_id: str, body: str) -> None:
    svc = _gmail()
    msg = svc.users().messages().get(userId="me", id=message_id, format="full").execute()
    thread_id = msg["threadId"]
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    to = headers.get("reply-to") or headers.get("from", "")
    subject = headers.get("subject", "")
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    raw = _build_mime(to, subject, body)
    out = svc.users().messages().send(
        userId="me", body={"raw": raw, "threadId": thread_id}
    ).execute()
    print(json.dumps({"reply_id": out["id"], "thread_id": thread_id}, indent=2))


# ----- calendar ------------------------------------------------------------

def _cal():
    return _service("calendar", "v3")


def calendar_list(calendar_id: str, time_from: str | None,
                  time_to: str | None, max_results: int) -> None:
    now = datetime.now(timezone.utc)
    start = datetime.fromisoformat(time_from) if time_from else now
    params = {
        "calendarId": calendar_id,
        "timeMin": _rfc3339(start),
        "singleEvents": True,
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    if time_to:
        params["timeMax"] = _rfc3339(time_to)
    items = _cal().events().list(**params).execute().get("items", [])
    out = []
    for e in items:
        s = e.get("start", {})
        out.append({
            "id": e["id"],
            "start": s.get("dateTime") or s.get("date"),
            "summary": e.get("summary"),
            "location": e.get("location"),
            "htmlLink": e.get("htmlLink"),
        })
    print(json.dumps(out, indent=2))


def calendar_create(summary: str, start: str, end: str,
                    description: str | None, location: str | None,
                    attendees: list[str] | None, calendar_id: str,
                    tz: str) -> None:
    body: dict = {
        "summary": summary,
        "start": {"dateTime": start, "timeZone": tz},
        "end": {"dateTime": end, "timeZone": tz},
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [{"email": e} for e in attendees]
    out = _cal().events().insert(calendarId=calendar_id, body=body).execute()
    print(json.dumps({"id": out["id"], "htmlLink": out.get("htmlLink")}, indent=2))


def calendar_list_calendars() -> None:
    items = _cal().calendarList().list().execute().get("items", [])
    out = [{
        "id": c["id"],
        "summary": c.get("summary"),
        "accessRole": c.get("accessRole"),
        "primary": c.get("primary", False),
    } for c in items]
    print(json.dumps(out, indent=2))


# ----- drive ---------------------------------------------------------------

def _drive():
    return _service("drive", "v3")


def drive_search(query: str, max_results: int) -> None:
    files = _drive().files().list(
        q=query, pageSize=max_results,
        fields="files(id, name, mimeType, modifiedTime, webViewLink)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute().get("files", [])
    print(json.dumps(files, indent=2))


def drive_list(folder: str | None, max_results: int) -> None:
    q = f"'{folder}' in parents and trashed = false" if folder else "trashed = false"
    drive_search(q, max_results)


# ----- meta ---------------------------------------------------------------

def whoami() -> None:
    sa_data = json.loads(_sa_path().read_text(encoding="utf-8"))
    print(json.dumps({
        "hermes_home": str(_hermes_home()),
        "sa_path": str(_sa_path()),
        "sa_client_email": sa_data["client_email"],
        "sa_project_id": sa_data["project_id"],
        "subject": _subject(),
    }, indent=2))


def check() -> None:
    try:
        items = _cal().calendarList().list().execute().get("items", [])
        print(json.dumps({"ok": True, "calendars_visible": len(items)}, indent=2))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2))
        sys.exit(1)


# ----- argparse -----------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser(prog="google_api.py (SA)", description=__doc__)
    sub = p.add_subparsers(dest="domain", required=True)

    # gmail
    pg = sub.add_parser("gmail").add_subparsers(dest="op", required=True)
    g1 = pg.add_parser("search"); g1.add_argument("query"); g1.add_argument("--max", type=int, default=10)
    g2 = pg.add_parser("get"); g2.add_argument("message_id")
    g3 = pg.add_parser("send")
    g3.add_argument("--to", required=True); g3.add_argument("--subject", required=True)
    g3.add_argument("--body", required=True); g3.add_argument("--cc"); g3.add_argument("--bcc")
    g4 = pg.add_parser("draft")
    g4.add_argument("--to", required=True); g4.add_argument("--subject", required=True)
    g4.add_argument("--body", required=True)
    g5 = pg.add_parser("reply")
    g5.add_argument("message_id"); g5.add_argument("--body", required=True)

    # calendar
    pc = sub.add_parser("calendar").add_subparsers(dest="op", required=True)
    c1 = pc.add_parser("list")
    c1.add_argument("--from", dest="from_"); c1.add_argument("--to", dest="to_")
    c1.add_argument("--calendar", default="primary"); c1.add_argument("--max", type=int, default=25)
    c2 = pc.add_parser("create")
    c2.add_argument("--summary", required=True); c2.add_argument("--start", required=True)
    c2.add_argument("--end", required=True); c2.add_argument("--description")
    c2.add_argument("--location"); c2.add_argument("--attendees", nargs="*")
    c2.add_argument("--calendar", default="primary"); c2.add_argument("--tz", default="Europe/Berlin")
    pc.add_parser("list-calendars")

    # drive
    pd = sub.add_parser("drive").add_subparsers(dest="op", required=True)
    d1 = pd.add_parser("search"); d1.add_argument("query"); d1.add_argument("--max", type=int, default=20)
    d2 = pd.add_parser("list"); d2.add_argument("--folder"); d2.add_argument("--max", type=int, default=20)

    # meta
    sub.add_parser("whoami")
    sub.add_parser("check")

    args = p.parse_args()

    if args.domain == "gmail":
        if args.op == "search":
            gmail_search(args.query, args.max)
        elif args.op == "get":
            gmail_get(args.message_id)
        elif args.op == "send":
            gmail_send(args.to, args.subject, args.body, args.cc, args.bcc)
        elif args.op == "draft":
            gmail_draft(args.to, args.subject, args.body)
        elif args.op == "reply":
            gmail_reply(args.message_id, args.body)
    elif args.domain == "calendar":
        if args.op == "list":
            calendar_list(args.calendar, args.from_, args.to_, args.max)
        elif args.op == "create":
            calendar_create(args.summary, args.start, args.end,
                            args.description, args.location, args.attendees,
                            args.calendar, args.tz)
        elif args.op == "list-calendars":
            calendar_list_calendars()
    elif args.domain == "drive":
        if args.op == "search":
            drive_search(args.query, args.max)
        elif args.op == "list":
            drive_list(args.folder, args.max)
    elif args.domain == "whoami":
        whoami()
    elif args.domain == "check":
        check()


if __name__ == "__main__":
    main()
