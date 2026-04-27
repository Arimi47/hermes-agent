import { NextResponse } from 'next/server';
import { readQuery } from '@/lib/neo4j';

// Vault hygiene endpoint - the same signal surface as the agent-side
// `mcp_graph_lint_vault` tool, exposed for Mission Control's Lint tab.
//
//   - Stubs: wikilink targets [[X]] referenced but never written as their
//     own .md file. Ranked by inbound MENTIONS count so high-degree entries
//     are the concepts you keep referring to without filing.
//   - Orphans: notes with no inbound MENTIONS or REFERS_TO. Folders that
//     are leaf-by-design (Daily / DailyLog / Template / Dashboard / Memory)
//     and the IngestRun singleton are excluded.
//   - Self-loops: a note that wikilinks itself (typo / copy-paste).
//   - Summary: total nodes, total Stubs, latest IngestRun metadata.

export const dynamic = 'force-dynamic';
export const revalidate = 0;

type StubRow = {
  id: { low: number; high: number } | number;
  name: string | null;
  mention_count: { low: number; high: number } | number;
};
type OrphanRow = {
  id: { low: number; high: number } | number;
  name: string | null;
  labels: string[];
  folder: string | null;
  path: string | null;
};
type LoopRow = {
  id: { low: number; high: number } | number;
  name: string | null;
  labels: string[];
  edge_type: string;
};
type SummaryRow = {
  total_nodes: { low: number; high: number } | number;
  total_stubs: { low: number; high: number } | number;
  last_ingest_at: string | null;
  last_ingest_files: { low: number; high: number } | number | null;
  last_ingest_mentions: { low: number; high: number } | number | null;
  last_ingest_refers: { low: number; high: number } | number | null;
};

const toInt = (v: { low: number; high: number } | number | null | undefined): number => {
  if (v == null) return 0;
  if (typeof v === 'number') return v;
  return v.low + v.high * 2 ** 32;
};

export async function GET(req: Request) {
  const url = new URL(req.url);
  const top = Math.min(200, Math.max(1, Number(url.searchParams.get('top') ?? '50')));
  const minDegree = Math.max(0, Number(url.searchParams.get('minStubDegree') ?? '1'));

  try {
    const [stubs, orphans, loops, summary] = await Promise.all([
      readQuery<StubRow>(
        `MATCH (s:Stub)
         OPTIONAL MATCH (s)<-[:MENTIONS]-(m)
         WITH s, count(m) AS mention_count
         WHERE mention_count >= $minDegree
         RETURN id(s) AS id, s.name AS name, mention_count
         ORDER BY mention_count DESC, name
         LIMIT $top`,
        { minDegree, top },
      ),
      readQuery<OrphanRow>(
        `MATCH (n)
         WHERE NOT n:Stub
           AND NOT n:Daily AND NOT n:DailyLog
           AND NOT n:Template AND NOT n:Dashboard
           AND NOT n:Memory AND NOT n:IngestRun
           AND NOT (n)<-[:MENTIONS]-()
           AND NOT (n)<-[:REFERS_TO]-()
         RETURN id(n) AS id, n.name AS name, labels(n) AS labels,
                n.folder AS folder, n.path AS path
         ORDER BY name
         LIMIT $top`,
        { top },
      ),
      readQuery<LoopRow>(
        `MATCH (n)-[r:MENTIONS|REFERS_TO]->(n)
         RETURN id(n) AS id, n.name AS name, labels(n) AS labels, type(r) AS edge_type
         ORDER BY name
         LIMIT 50`,
      ),
      readQuery<SummaryRow>(
        `CALL { MATCH (n) WHERE NOT n:IngestRun RETURN count(n) AS total_nodes }
         CALL { MATCH (s:Stub) RETURN count(s) AS total_stubs }
         OPTIONAL MATCH (i:IngestRun {key: 'latest'})
         RETURN total_nodes, total_stubs,
                toString(i.at) AS last_ingest_at,
                i.files AS last_ingest_files,
                i.mentions AS last_ingest_mentions,
                i.refers AS last_ingest_refers`,
      ),
    ]);

    return NextResponse.json({
      summary: summary[0]
        ? {
            total_nodes: toInt(summary[0].total_nodes),
            total_stubs: toInt(summary[0].total_stubs),
            last_ingest_at: summary[0].last_ingest_at,
            last_ingest_files: toInt(summary[0].last_ingest_files),
            last_ingest_mentions: toInt(summary[0].last_ingest_mentions),
            last_ingest_refers: toInt(summary[0].last_ingest_refers),
          }
        : null,
      stubs: stubs.map((s) => ({
        id: toInt(s.id),
        name: s.name ?? '(unnamed)',
        mention_count: toInt(s.mention_count),
      })),
      orphans: orphans.map((o) => ({
        id: toInt(o.id),
        name: o.name ?? '(unnamed)',
        labels: o.labels ?? [],
        folder: o.folder,
        path: o.path,
      })),
      self_loops: loops.map((l) => ({
        id: toInt(l.id),
        name: l.name ?? '(unnamed)',
        labels: l.labels ?? [],
        edge_type: l.edge_type,
      })),
    });
  } catch (e) {
    return NextResponse.json(
      { error: (e as Error).message },
      { status: 500 },
    );
  }
}
