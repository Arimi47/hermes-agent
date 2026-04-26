"""Hermes graph MCP server.

Exposes five read-only Cypher-backed tools so Hermes can ask "what do I
know about X" as part of its reasoning. All tools return plain Python
values; FastMCP serialises to JSON. The Neo4j driver is reused across
calls via a module-level GraphDatabase handle.
"""
from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from neo4j import GraphDatabase

NEO4J_URI = os.environ["NEO4J_URI"]
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ["NEO4J_PASSWORD"]

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
mcp = FastMCP("hermes-graph")


def _run(query: str, **params: Any) -> list[dict]:
    with driver.session(default_access_mode="READ") as s:
        return [dict(r) for r in s.run(query, **params)]


@mcp.tool()
def entity_lookup(name: str) -> dict:
    """Find entities matching `name` (exact or case-insensitive contains).

    Returns a list of matches, each with labels, all properties, and a
    short list of direct neighbours. Start here for "what do I know
    about X" queries.
    """
    rows = _run(
        """
        MATCH (n)
        WHERE toLower(n.name) = toLower($name)
           OR toLower(n.name) CONTAINS toLower($name)
        OPTIONAL MATCH (n)-[:MENTIONS]-(nb)
        WITH n, collect(DISTINCT nb.name)[0..10] AS neighbours
        RETURN n.name AS name,
               labels(n) AS labels,
               properties(n) AS props,
               neighbours
        LIMIT 10
        """,
        name=name,
    )
    return {"matches": rows, "count": len(rows)}


@mcp.tool()
def neighbors(name: str, depth: int = 1) -> dict:
    """Return the 1- or 2-hop neighbourhood of a named entity.

    depth=1 gives direct connections; depth=2 gives neighbours of
    neighbours (use sparingly - can return hundreds of nodes for central
    entities like [[EstateMate]] or [[Birnbaum Group]]).
    """
    depth = 1 if depth not in (1, 2) else depth
    rows = _run(
        f"""
        MATCH (n {{name: $name}})
        OPTIONAL MATCH (n)-[:MENTIONS*1..{depth}]-(nb)
        WITH DISTINCT nb
        WHERE nb IS NOT NULL
        RETURN nb.name AS name, labels(nb) AS labels
        ORDER BY name
        LIMIT 200
        """,
        name=name,
    )
    return {"origin": name, "depth": depth, "neighbours": rows, "count": len(rows)}


@mcp.tool()
def recent_entities(hours: int = 48, limit: int = 20) -> dict:
    """Recently-mentioned entities: ranked by how many Daily notes from
    the last `hours` window link to them. Good for "what's hot right now"
    style questions.
    """
    # date() is identity on Neo4j Date, parses ISO strings, extracts date
    # from DateTime. Safer than datetime() casting which would reject the
    # plain Date values written by the YAML frontmatter ingester.
    rows = _run(
        """
        MATCH (d:Daily)-[:MENTIONS]->(e)
        WHERE d.date IS NOT NULL
          AND date(d.date) > date() - duration({days: $days})
        WITH e, count(DISTINCT d) AS mentions
        RETURN e.name AS name, labels(e) AS labels, mentions
        ORDER BY mentions DESC
        LIMIT $limit
        """,
        days=max(1, hours // 24), limit=limit,
    )
    return {"window_hours": hours, "entities": rows}


@mcp.tool()
def shortest_path(a: str, b: str, max_length: int = 6) -> dict:
    """Shortest MENTIONS path between two named entities.

    Returns the list of node names and labels along the path, or an
    empty result if no path exists within `max_length` hops. Useful for
    "how is X connected to Y".
    """
    rows = _run(
        f"""
        MATCH (a {{name: $a}}), (b {{name: $b}}),
              p = shortestPath((a)-[:MENTIONS*..{max_length}]-(b))
        UNWIND nodes(p) AS n
        RETURN n.name AS name, labels(n) AS labels
        """,
        a=a, b=b,
    )
    return {"from": a, "to": b, "path": rows, "length": max(0, len(rows) - 1)}


@mcp.tool()
def graph_query_cypher(query: str) -> dict:
    """Escape hatch: run a raw Cypher query (read-only). Use when the
    typed tools above don't fit. The session runs in READ mode so write
    statements are rejected at the driver level.
    """
    rows = _run(query)
    return {"rows": rows, "count": len(rows)}


@mcp.tool()
def lint_vault(top_n: int = 30, min_stub_degree: int = 1) -> dict:
    """Vault health report. Surfaces graph-internal hygiene issues:

    - Unresolved Stubs: wikilink targets [[X]] that were referenced
      but never written as their own .md file. Ranked by inbound
      MENTIONS count, so high-degree entries are concepts the user
      keeps referring to without filing.
    - Orphan notes: notes with no inbound MENTIONS or REFERS_TO edges.
      Excludes folders that are leaf-by-design (Daily, DailyLog,
      Template, Dashboard, Memory) and the IngestRun singleton.
    - Self-loops: a note that wikilinks itself, usually a typo or a
      copy-paste accident.

    Plus a summary header with total node count, total Stub count, and
    the last ingest run's metadata.

    Use when Ari asks: "vault check", "lint", "vault health", "wo sind
    tote links", "was ist im wiki kaputt", "stubs".

    Provenance / source-frontmatter checks are intentionally NOT in this
    report - the vault is first-party authored, not synthesised from
    external documents. Add provenance lint once OneDrive/Drive
    ingestion lands.
    """
    stubs = _run(
        """
        MATCH (s:Stub)
        OPTIONAL MATCH (s)<-[:MENTIONS]-(m)
        WITH s, count(m) AS mention_count
        WHERE mention_count >= $min_degree
        RETURN s.name AS name, mention_count
        ORDER BY mention_count DESC, name
        LIMIT $top_n
        """,
        min_degree=min_stub_degree, top_n=top_n,
    )

    orphans = _run(
        """
        MATCH (n)
        WHERE NOT n:Stub
          AND NOT n:Daily AND NOT n:DailyLog
          AND NOT n:Template AND NOT n:Dashboard
          AND NOT n:Memory AND NOT n:IngestRun
          AND NOT (n)<-[:MENTIONS]-()
          AND NOT (n)<-[:REFERS_TO]-()
        RETURN n.name AS name, labels(n) AS labels,
               n.folder AS folder, n.path AS path
        ORDER BY name
        LIMIT $top_n
        """,
        top_n=top_n,
    )

    self_loops = _run(
        """
        MATCH (n)-[r:MENTIONS|REFERS_TO]->(n)
        RETURN n.name AS name, labels(n) AS labels, type(r) AS edge_type
        ORDER BY name
        LIMIT 50
        """,
    )

    summary = _run(
        """
        CALL { MATCH (n) WHERE NOT n:IngestRun RETURN count(n) AS total_nodes }
        CALL { MATCH (s:Stub) RETURN count(s) AS total_stubs }
        OPTIONAL MATCH (i:IngestRun {key: 'latest'})
        RETURN total_nodes, total_stubs,
               toString(i.at) AS last_ingest_at,
               i.files AS last_ingest_files,
               i.mentions AS last_ingest_mentions,
               i.refers AS last_ingest_refers,
               i.duration_ms AS last_ingest_duration_ms,
               i.error AS last_ingest_error
        """
    )

    return {
        "summary": summary[0] if summary else {},
        "unresolved_stubs": {
            "filter_min_degree": min_stub_degree,
            "count_returned": len(stubs),
            "items": stubs,
        },
        "orphan_notes": {
            "count_returned": len(orphans),
            "items": orphans,
        },
        "self_loops": {
            "count_returned": len(self_loops),
            "items": self_loops,
        },
    }


if __name__ == "__main__":
    mcp.run()
