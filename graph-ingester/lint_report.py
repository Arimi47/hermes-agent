"""Weekly vault lint report.

Runs the same lint Cypher as graph-mcp/server.py:lint_vault and the
mission-control /api/lint route, formats the result as markdown, and
writes Dashboards/Lint Report - YYYY-WWNN.md into the Obsidian vault.

Idempotent: if this ISO week's file already exists, exit 0 without
writing or committing anything. The wrapper loop in start.sh ticks
hourly; the first tick after the ISO-week rollover (typically very
early Monday Berlin time) creates the new report. Subsequent ticks
in the same week are no-ops.

The committed file becomes:
  - a Dashboard node in the Neo4j graph next ingest pass
  - visible in Obsidian via the 2-way GitHub sync
  - a snapshot in vault git history, so trends are diff-able
"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/data/vault"))
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

DASHBOARDS_DIR = VAULT_PATH / "Dashboards"


def iso_week_label(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def report_path(now: datetime) -> Path:
    return DASHBOARDS_DIR / f"Lint Report - {iso_week_label(now)}.md"


def fetch_lint(driver) -> dict[str, Any]:
    with driver.session(default_access_mode="READ") as s:
        stubs = [dict(r) for r in s.run(
            """
            MATCH (s:Stub)
            OPTIONAL MATCH (s)<-[:MENTIONS]-(m)
            WITH s, count(m) AS mention_count
            WHERE mention_count >= 1
            RETURN s.name AS name, mention_count
            ORDER BY mention_count DESC, name
            LIMIT 100
            """
        )]
        orphans = [dict(r) for r in s.run(
            """
            MATCH (n)
            WHERE NOT n:Stub
              AND NOT n:Daily AND NOT n:DailyLog
              AND NOT n:Template AND NOT n:Dashboard
              AND NOT n:Memory AND NOT n:IngestRun
              AND NOT (n)<-[:MENTIONS]-()
              AND NOT (n)<-[:REFERS_TO]-()
            RETURN n.name AS name, labels(n) AS labels, n.folder AS folder
            ORDER BY name
            LIMIT 200
            """
        )]
        loops = [dict(r) for r in s.run(
            """
            MATCH (n)-[r:MENTIONS|REFERS_TO]->(n)
            RETURN n.name AS name, labels(n) AS labels, type(r) AS edge_type
            ORDER BY name
            LIMIT 50
            """
        )]
        summary_rows = [dict(r) for r in s.run(
            """
            CALL { MATCH (n) WHERE NOT n:IngestRun RETURN count(n) AS total_nodes }
            CALL { MATCH (s:Stub) RETURN count(s) AS total_stubs }
            OPTIONAL MATCH (i:IngestRun {key: 'latest'})
            RETURN total_nodes, total_stubs,
                   toString(i.at) AS last_ingest_at,
                   i.files AS last_ingest_files
            """
        )]
    return {
        "summary": summary_rows[0] if summary_rows else {},
        "stubs": stubs,
        "orphans": orphans,
        "self_loops": loops,
    }


def primary_label(labels: list[str] | None) -> str:
    for label in labels or []:
        if label != "Stub":
            return label
    return "Note"


def render_md(label: str, now: datetime, lint: dict[str, Any]) -> str:
    s = lint["summary"]
    iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = [
        "---",
        "type: dashboard",
        f"week: {label}",
        f"generated: {iso}",
        "---",
        "",
        f"# Vault lint report - {label}",
        "",
        "Auto-generated weekly snapshot of vault hygiene. Click any [[wikilink]] in Obsidian to jump to that note.",
        "",
        "## Summary",
        "",
        f"- Total nodes: **{s.get('total_nodes', 0)}**",
        f"- Unresolved stubs: **{s.get('total_stubs', 0)}**",
        f"- Orphan notes in this report: **{len(lint['orphans'])}**",
        f"- Self-loops in this report: **{len(lint['self_loops'])}**",
        f"- Last ingest: {s.get('last_ingest_at') or '(unknown)'} - {s.get('last_ingest_files', 0)} files",
        "",
        "## Unresolved stubs",
        "",
        "Wikilinks you wrote but never created the page for, ranked by inbound mention count. High counts are concepts you keep referring to without filing - prime candidates for promotion.",
        "",
    ]
    if lint["stubs"]:
        for stub in lint["stubs"]:
            count = stub.get("mention_count", 0)
            lines.append(f"- [[{stub['name']}]] - **{count}x**")
    else:
        lines.append("- _no unresolved stubs._")
    lines.extend([
        "",
        "## Orphan notes",
        "",
        "Notes with no inbound MENTIONS or REFERS_TO edges. Excludes leaf-by-design folders (Daily, DailyLog, Template, Dashboard, Memory).",
        "",
    ])
    if lint["orphans"]:
        for o in lint["orphans"]:
            primary = primary_label(o.get("labels"))
            folder = o.get("folder") or "(root)"
            lines.append(f"- [[{o['name']}]] - _{primary} in {folder}_")
    else:
        lines.append("- _no orphan notes._")
    lines.extend([
        "",
        "## Self-loops",
        "",
        "Notes that wikilink themselves. Usually a typo or a copy-paste accident.",
        "",
    ])
    if lint["self_loops"]:
        for loop in lint["self_loops"]:
            edge = (loop.get("edge_type") or "?").lower()
            lines.append(f"- [[{loop['name']}]] - _{edge}_")
    else:
        lines.append("- _no self-loops._")
    lines.append("")
    return "\n".join(lines)


def commit_and_push(path: Path, label: str) -> None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        subprocess.run(
            ["git", "-C", str(VAULT_PATH), "add", str(path)],
            check=True, env=env, timeout=30,
        )
        msg = f"Hermes: Lint report {label}"
        r = subprocess.run(
            ["git", "-C", str(VAULT_PATH), "commit", "-m", msg],
            capture_output=True, text=True, env=env, timeout=30,
        )
        if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
            print(f"commit warning: {(r.stdout + r.stderr).strip()[:200]}", file=sys.stderr)
            return
        subprocess.run(
            ["git", "-C", str(VAULT_PATH), "push", "origin", "HEAD"],
            check=False, env=env, timeout=60,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"git error: {e}", file=sys.stderr)


def main() -> int:
    now = datetime.now(timezone.utc)
    label = iso_week_label(now)
    out = report_path(now)
    if out.exists():
        print(f"skip: {out.name} already exists")
        return 0
    if not VAULT_PATH.exists():
        print(f"skip: vault path missing at {VAULT_PATH}")
        return 0

    DASHBOARDS_DIR.mkdir(parents=True, exist_ok=True)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
        lint = fetch_lint(driver)
    except Exception as e:
        print(f"neo4j error: {e}", file=sys.stderr)
        return 1
    finally:
        driver.close()

    md = render_md(label, now, lint)
    out.write_text(md, encoding="utf-8")
    print(f"wrote {out.relative_to(VAULT_PATH)}")
    commit_and_push(out, label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
