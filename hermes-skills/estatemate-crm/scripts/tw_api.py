"""Shared Twenty API helpers for estatemate-crm skill."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _get_env(name: str) -> str:
    v = os.environ.get(name)
    if not v:
        sys.exit(f"Missing environment variable: {name}")
    return v


BASE = _get_env("TWENTY_BASE_URL").rstrip("/")
TOKEN = _get_env("TWENTY_API_KEY")
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def api(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, e.read().decode(errors="replace")


def list_all(plural: str, key: str, limit: int = 60) -> list[dict]:
    code, resp = api("GET", f"/rest/{plural}?limit={limit}")
    if code >= 300 or not isinstance(resp, dict):
        return []
    data = resp.get("data", {})
    if isinstance(data, dict):
        return data.get(key, [])
    return data if isinstance(data, list) else []


def extract_created_id(resp: dict) -> str | None:
    data = resp.get("data", {}) if isinstance(resp, dict) else {}
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, dict) and "id" in v:
                return v["id"]
    return None


def fail(msg: str, detail: object = None) -> None:
    payload = {"ok": False, "error": msg}
    if detail is not None:
        payload["detail"] = detail
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    sys.exit(1)


def success(payload: dict) -> None:
    print(json.dumps({"ok": True, **payload}, ensure_ascii=False, indent=2))


def find_person_by_name(query: str) -> list[dict]:
    """Case-insensitive substring match on first+last name."""
    q = query.lower()
    out = []
    for p in list_all("people", "people", limit=100):
        n = p.get("name", {}) or {}
        full = f"{n.get('firstName','')} {n.get('lastName','')}".lower()
        if q in full:
            out.append(p)
    return out


def find_by_name(plural: str, key: str, query: str) -> list[dict]:
    q = query.lower()
    out = []
    for r in list_all(plural, key, limit=100):
        name = r.get("name") or ""
        if isinstance(name, str) and q in name.lower():
            out.append(r)
    return out
