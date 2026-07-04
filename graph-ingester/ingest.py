"""Vault -> Neo4j ingester.

Walks /data/vault recursively, parses YAML frontmatter + wikilinks, and
upserts nodes + edges into Neo4j via idempotent MERGE queries. Safe to
run repeatedly; node labels reflect folder structure, edge labels
reflect folder-pairing + "MENTIONS" for generic prose wikilinks.

Every node carries the :Entity base label, backed by a uniqueness
constraint on Entity.name (see ensure_schema). All MERGE/MATCH patterns
go through :Entity so they hit the constraint's index — a label-less
`MERGE (n {name})` cannot use any index and degenerates to a full node
scan per file, per pass.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import frontmatter
from neo4j import GraphDatabase, Driver, unit_of_work

VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_PATH", "/data/vault"))
NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

# Heartbeat file, written on EVERY run outcome — especially when Neo4j
# itself is down (the IngestRun node can't record that case: writing it
# requires the very DB that just failed). "Ingest hasn't succeeded in N
# minutes" is detectable from this file's content/mtime via railway ssh
# or the admin server, without a working graph.
STATUS_FILE = Path(os.environ.get(
    "GRAPH_INGEST_STATUS_FILE", "/data/.hermes/graph-ingest-status.json"))

# A hung Neo4j must not stall the ingest loop forever: start.sh runs this
# script sequentially, so without deadlines one stuck query would silently
# stop all future passes. Driver-level connect deadlines + server-side
# transaction timeouts bound every network interaction.
DRIVER_KWARGS = dict(
    connection_timeout=15,
    connection_acquisition_timeout=30,
    max_transaction_retry_time=30,
)
TX_TIMEOUT = 60  # seconds, enforced server-side per transaction
BATCH_SIZE = 500  # rows per UNWIND transaction

# If the walk sees less than this fraction of the previous run's file
# count, assume a partial checkout (the 60s vault git loop rebases while
# we walk) and skip the stale-node cleanup for this pass.
CLEANUP_SHRINK_FLOOR = 0.7

# Folder name (lowercased, trimmed of leading numeric prefix like "02 - ")
# to Neo4j label.
FOLDER_LABEL = {
    "people": "Person",
    "companies": "Company",
    "properties": "Property",
    "leads": "Lead",
    "tasks": "Task",
    "projects": "Project",
    "01 - daily": "Daily",
    "daily": "Daily",
    "daily logs": "DailyLog",
    "dashboards": "Dashboard",
    "claude memory": "Memory",
    "templates": "Template",
    "documents": "Document",
    "docs": "Doc",
}

# Wikilink regex: [[target]] or [[target|alias]]. Alias is display-only.
WIKILINK_RE = re.compile(r"\[\[([^\[\]\|]+?)(?:\|[^\[\]]*)?\]\]")


def folder_of(path: Path) -> str:
    """Top-level folder under the vault, or empty string for root files."""
    rel = path.relative_to(VAULT_PATH)
    parts = rel.parts
    return parts[0] if len(parts) > 1 else ""


def label_for(folder: str, fallback: str = "Note") -> str:
    key = folder.lower().lstrip()
    # strip a leading "NN - " numeric prefix if present (so "02 - Projects" -> "projects")
    m = re.match(r"^\d+\s*-\s*(.*)$", key)
    if m:
        key = m.group(1)
    return FOLDER_LABEL.get(key, fallback)


def node_name(path: Path) -> str:
    """Filename without .md extension, used as canonical node identity."""
    return path.stem


def walk_vault() -> Iterable[Path]:
    for p in VAULT_PATH.rglob("*.md"):
        # skip hidden / .obsidian / .trash dirs
        if any(part.startswith(".") for part in p.relative_to(VAULT_PATH).parts):
            continue
        yield p


def extract_wikilinks(content: str) -> list[str]:
    """Return de-duplicated wikilink targets (filename-only, no alias)."""
    seen: dict[str, None] = {}
    for target in WIKILINK_RE.findall(content):
        # Obsidian may include "folder/name" or "name#heading" - normalise to basename.
        target = target.split("#", 1)[0].split("^", 1)[0].strip()
        target = target.rsplit("/", 1)[-1]
        if target and target not in seen:
            seen[target] = None
    return list(seen)


def ensure_schema(driver: Driver) -> None:
    """Idempotent schema setup, runs every pass.

    1. Migration: promote pre-Entity nodes (created by older ingester
       versions) to :Entity. No-op scan once everything is labeled.
       IngestRun is excluded — it is keyed by `key`, not `name`.
    2. Uniqueness constraint on Entity.name. This is what makes every
       MERGE below an index lookup instead of a full node scan, and it
       is the DB-level guarantee against duplicate-name nodes that the
       app-level two-phase MERGE alone cannot give.

    Constraint creation fails if duplicate names already exist; that is
    logged loudly (every pass) instead of auto-deduped, because merging
    duplicates means merging their edges — a call for a human.
    """
    @unit_of_work(timeout=300)
    def migrate(tx):
        tx.run(
            """
            MATCH (n)
            WHERE n.name IS NOT NULL AND NOT n:Entity AND NOT n:IngestRun
            SET n:Entity
            """
        )

    with driver.session() as s:
        s.execute_write(migrate)
        try:
            # Schema DDL is not allowed inside transaction functions —
            # auto-commit is the correct mode here.
            s.run(
                "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE n.name IS UNIQUE"
            ).consume()
        except Exception as e:
            print(
                f"[schema] entity_name_unique constraint not active "
                f"(duplicate names in graph? needs manual dedupe): {e}",
                file=sys.stderr,
            )


@unit_of_work(timeout=TX_TIMEOUT)
def upsert_nodes(tx, label: str, rows: list[dict]) -> None:
    """Idempotent batch-MERGE on :Entity(name), then assign folder label.

    Matching on Entity+name (no folder label in the pattern) is critical:
    otherwise a previously-created Stub node (from a wikilink referencing
    this entity before its own file was walked) would NOT match
    `MERGE (n:Label {name})`, and we'd end up with two distinct nodes for
    the same entity. Two-phase approach instead: match-by-name, then
    promote via SET label + REMOVE Stub.
    """
    tx.run(
        f"""
        UNWIND $rows AS row
        MERGE (n:Entity {{name: row.name}})
        SET n:{label}
        REMOVE n:Stub
        SET n += row.props
        """,
        rows=rows,
    )


@unit_of_work(timeout=TX_TIMEOUT)
def upsert_mentions(tx, pairs: list[dict]) -> None:
    """MENTIONS edges from already-created sources to target nodes.

    Sources are guaranteed to exist because ingest() upserts all nodes
    first. Targets are matched by name; if no node with that name exists
    yet, create a Stub. A later pass promotes the Stub via upsert_nodes'
    SET/REMOVE.
    """
    tx.run(
        """
        UNWIND $pairs AS p
        MATCH (src:Entity {name: p.src})
        MERGE (tgt:Entity {name: p.tgt})
        ON CREATE SET tgt:Stub
        MERGE (src)-[:MENTIONS]->(tgt)
        """,
        pairs=pairs,
    )


# YAML keys that never reference another entity - don't scan their values
# for edges. Everything else is fair game (assignee, area, eigentuemer,
# hausmeister, rolle, firma, mieter, kontakt, portfolio, ...).
SCALAR_YAML_KEYS = {
    'status', 'priority', 'deadline', 'date', 'type', 'id', 'mfiles_id',
    'email', 'url', 'phone', 'path', 'folder', 'tags', 'aliases',
    'created', 'modified', 'updated', 'version', 'draft', 'cssclass',
    'title', 'description', 'summary', 'icon', 'color', 'location',
    'standort', 'adresse',
}


def _unwrap_wikilink(v: str) -> str:
    """Hermes writes many YAML refs as proper wikilinks
    (eigentuemer: '[[XYZ GbR]]') so Obsidian still tracks them in the
    native graph view. Strip the brackets + alias before matching."""
    s = v.strip()
    if s.startswith('[[') and s.endswith(']]'):
        s = s[2:-2]
    # handle [[name|alias]] -> name
    if '|' in s:
        s = s.split('|', 1)[0]
    # handle [[name#heading]] -> name
    s = s.split('#', 1)[0].split('^', 1)[0]
    return s.strip()


def yaml_refs(src_name: str, props: dict) -> list[dict]:
    """Candidate REFERS_TO rows from YAML props: every string value that
    could name another entity, tagged with its YAML key. Resolution
    against the graph happens in upsert_yaml_edges."""
    rows = []
    for key, raw in props.items():
        if key in SCALAR_YAML_KEYS:
            continue
        values = raw if isinstance(raw, list) else [raw]
        for v in values:
            if not isinstance(v, str):
                continue
            tgt = _unwrap_wikilink(v)
            if not tgt or tgt == src_name:
                continue
            rows.append({"src": src_name, "tgt": tgt, "via": key})
    return rows


@unit_of_work(timeout=TX_TIMEOUT)
def upsert_yaml_edges(tx, rows: list[dict]) -> int:
    """Materialise REFERS_TO edges where both ends are real nodes.

    Uses MATCH (not MERGE) for the target so we never create stubs from
    YAML - only materialise edges when both ends exist. That keeps the
    graph honest: a YAML value `eigentuemer: "ACME GbR"` only produces
    an edge if we actually have a Companies/ACME GbR.md file.
    """
    res = tx.run(
        """
        UNWIND $rows AS row
        MATCH (src:Entity {name: row.src})
        MATCH (tgt:Entity {name: row.tgt})
        WHERE elementId(src) <> elementId(tgt)
        MERGE (src)-[r:REFERS_TO {via: row.via}]->(tgt)
        RETURN count(r) AS n
        """,
        rows=rows,
    ).single()
    return res["n"] if res else 0


@unit_of_work(timeout=TX_TIMEOUT)
def cleanup_stale(tx, seen_paths: list[str]) -> int:
    """Delete file-backed nodes whose path is no longer in the vault.

    Necessary because earlier passes only upsert. When a file is renamed
    or deleted, the old node stays in the graph with a stale path,
    which produces ghost entries in the Mission Control task board and
    breaks the mark-done write-back (POST /api/vault/task/status returns
    'invalid or unknown path' for files that no longer exist).

    Preserved categories (NOT deleted):
      - :Stub nodes (no `path` property; unresolved wikilink targets)
      - :IngestRun singleton (no `path`; metadata)
      - Any other property-only node added in the future without `path`

    Returns the number of nodes deleted.
    """
    res = tx.run(
        """
        MATCH (n:Entity)
        WHERE n.path IS NOT NULL
          AND NOT n.path IN $paths
        WITH n, count(n) AS _
        DETACH DELETE n
        RETURN count(_) AS deleted
        """,
        paths=seen_paths,
    ).single()
    return res["deleted"] if res else 0


@unit_of_work(timeout=TX_TIMEOUT)
def previous_file_count(tx) -> int | None:
    rec = tx.run(
        "MATCH (r:IngestRun {key: 'latest'}) RETURN r.files AS files"
    ).single()
    return rec["files"] if rec and rec["files"] is not None else None


def chunked(rows: list, size: int = BATCH_SIZE) -> Iterable[list]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def ingest(driver: Driver) -> tuple[int, int, int, int]:
    """Four-pass walk:
      1. Upsert all labeled nodes (so wikilink targets match existing
         labeled nodes instead of spawning Stubs).
      2. MENTIONS edges from [[wikilinks]] in the content.
      3. REFERS_TO edges from YAML props whose string values match
         existing node names (promotes "eigentuemer: X" style
         references to graph edges).
      4. Cleanup pass: delete file-backed nodes whose path is no longer
         in the vault (handles renames and deletes; safe because Stubs
         and IngestRun have no `path` property).

    Writes are batched (UNWIND, BATCH_SIZE rows per transaction) — one
    round-trip per batch instead of one per node/edge.
    """
    files = 0
    deleted = 0
    parsed: list[tuple[str, str, str, dict]] = []
    seen_paths: list[str] = []
    for path in walk_vault():
        rel_path = str(path.relative_to(VAULT_PATH))
        # The file exists on disk, so its node must survive cleanup even
        # if this particular read/parse fails — a transient YAML syntax
        # error must not DETACH DELETE the node and all its edges.
        seen_paths.append(rel_path)
        try:
            post = frontmatter.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            print(f"[skip] {path}: {e}", file=sys.stderr)
            continue
        name = node_name(path)
        folder = folder_of(path)
        label = label_for(folder)
        meta = {k: v for k, v in post.metadata.items() if v is not None}
        meta["path"] = rel_path
        meta["folder"] = folder
        parsed.append((name, label, post.content, meta))

    # Group node rows by label: the label lives in the Cypher text (labels
    # can't be parameterised), so one batched statement per label.
    by_label: dict[str, list[dict]] = {}
    mention_pairs: list[dict] = []
    yaml_rows: list[dict] = []
    for name, label, content, meta in parsed:
        # Node props must be Neo4j-storable scalars; yaml_refs below still
        # sees the full metadata (list values like `mieter: [A, B]` are
        # edge sources, just not node properties).
        props = {k: v for k, v in meta.items() if not isinstance(v, (dict, list))}
        by_label.setdefault(label, []).append({"name": name, "props": props})
        for target in extract_wikilinks(content):
            mention_pairs.append({"src": name, "tgt": target})
        yaml_rows.extend(yaml_refs(name, meta))

    refer_edges = 0
    with driver.session() as session:
        for label, rows in by_label.items():
            for batch in chunked(rows):
                session.execute_write(upsert_nodes, label, batch)
                files += len(batch)
        for batch in chunked(mention_pairs):
            session.execute_write(upsert_mentions, batch)
        # Pass 3 runs AFTER all wikilink edges so YAML-derived
        # REFERS_TO edges see the full node set.
        for batch in chunked(yaml_rows):
            refer_edges += session.execute_write(upsert_yaml_edges, batch)

        # Pass 4 guards:
        #   - files > 0: a transient empty walk (mid-clone) cannot wipe
        #     the graph.
        #   - shrink floor: the 60s vault git loop rebases while we walk,
        #     so a partial checkout can present a shrunken file set. If
        #     this walk saw far fewer files than the last recorded run,
        #     skip cleanup and let the next pass (over a settled tree)
        #     handle deletions.
        prev = session.execute_read(previous_file_count)
        shrunk = (
            prev is not None and prev >= 20
            and len(seen_paths) < CLEANUP_SHRINK_FLOOR * prev
        )
        if files > 0 and not shrunk:
            deleted = session.execute_write(cleanup_stale, seen_paths)
        elif shrunk:
            print(
                f"[cleanup-skipped] walk saw {len(seen_paths)} files vs "
                f"{prev} last run (<{int(CLEANUP_SHRINK_FLOOR * 100)}%) - "
                f"assuming partial vault checkout",
                file=sys.stderr,
            )
    return files, len(mention_pairs), refer_edges, deleted


def record_run(driver: Driver, files: int, mentions: int, refers: int, deleted: int, duration_ms: int, error: str | None = None) -> None:
    """Writes a singleton IngestRun node so Mission Control can show
    'last ingest N seconds ago' without SSH'ing to the container."""
    @unit_of_work(timeout=TX_TIMEOUT)
    def write(tx):
        tx.run(
            """
            MERGE (r:IngestRun {key: 'latest'})
            SET r.at = datetime(),
                r.files = $files,
                r.mentions = $mentions,
                r.refers = $refers,
                r.deleted = $deleted,
                r.duration_ms = $duration_ms,
                r.error = $error
            """,
            files=files, mentions=mentions, refers=refers, deleted=deleted,
            duration_ms=duration_ms, error=error,
        )

    with driver.session() as s:
        s.execute_write(write)


def write_status(payload: dict) -> None:
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATUS_FILE.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(STATUS_FILE)
    except Exception as e:
        print(f"[ingest-status-failed] {e}", file=sys.stderr)


def main() -> None:
    import time
    driver = GraphDatabase.driver(
        NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), **DRIVER_KWARGS)
    t0 = time.time()
    err = None
    files = mentions = refers = deleted = 0
    try:
        driver.verify_connectivity()
        ensure_schema(driver)
        files, mentions, refers, deleted = ingest(driver)
        print(
            f"[ingest] {files} nodes, {mentions} MENTIONS, "
            f"{refers} REFERS_TO, {deleted} stale deleted from {VAULT_PATH}"
        )
    except Exception as e:
        err = str(e)
        print(f"[ingest-error] {err}", file=sys.stderr)
        raise
    finally:
        duration_ms = int((time.time() - t0) * 1000)
        write_status({
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "ok": err is None,
            "files": files,
            "mentions": mentions,
            "refers": refers,
            "deleted": deleted,
            "duration_ms": duration_ms,
            "error": err,
        })
        try:
            record_run(driver, files, mentions, refers, deleted, duration_ms, err)
        except Exception as log_err:
            print(f"[ingest-record-failed] {log_err}", file=sys.stderr)
        driver.close()


if __name__ == "__main__":
    main()
