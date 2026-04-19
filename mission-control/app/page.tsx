import { readQuery } from '@/lib/neo4j';

// Server Component - runs per-request on the Node server, reads Neo4j
// via Bolt, renders HTML. No client JS needed for the stats panel.
export const dynamic = 'force-dynamic';
export const revalidate = 0;

type LabelCount = { label: string; n: { low: number; high: number } | number };

async function loadStats() {
  const [totalRow] = await readQuery<{ total: { low: number; high: number } | number }>(
    'MATCH (n) RETURN count(n) AS total',
  );
  const [edgesRow] = await readQuery<{ edges: { low: number; high: number } | number }>(
    'MATCH ()-[r]->() RETURN count(r) AS edges',
  );
  const labels = await readQuery<LabelCount>(
    'MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY n DESC',
  );
  const toInt = (v: LabelCount['n']) =>
    typeof v === 'number' ? v : v.low + v.high * 2 ** 32;
  return {
    total: toInt(totalRow.total),
    edges: toInt(edgesRow.edges),
    labels: labels.map((l) => ({ label: l.label ?? 'unlabeled', n: toInt(l.n) })),
  };
}

export default async function Page() {
  try {
    const stats = await loadStats();
    return (
      <main>
        <h1>Hermes Mission Control</h1>
        <div className="stat-row">
          <div className="stat">
            <div className="stat-label">Nodes</div>
            <div className="stat-value">{stats.total}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Edges</div>
            <div className="stat-value">{stats.edges}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Labels</div>
            <div className="stat-value">{stats.labels.length}</div>
          </div>
        </div>
        <div className="label-list">
          <h2>Label breakdown</h2>
          {stats.labels.map((l) => (
            <div className="label-row" key={l.label}>
              <span className="label-name">{l.label}</span>
              <span className="label-count">{l.n}</span>
            </div>
          ))}
        </div>
      </main>
    );
  } catch (e) {
    return (
      <main>
        <h1>Hermes Mission Control</h1>
        <div className="err">
          Neo4j connect failed: {(e as Error).message}
        </div>
      </main>
    );
  }
}
