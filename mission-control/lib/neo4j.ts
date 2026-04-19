import neo4j, { Driver } from 'neo4j-driver';

// Singleton driver so repeated Server Component renders reuse the
// connection pool. Next.js dev mode hot-reloads modules; the `globalThis`
// stash survives the reload.
const g = globalThis as unknown as { __neo4jDriver?: Driver };

function make(): Driver {
  const uri = process.env.NEO4J_URI;
  const user = process.env.NEO4J_USER ?? 'neo4j';
  const pwd = process.env.NEO4J_PASSWORD;
  if (!uri || !pwd) {
    throw new Error('NEO4J_URI and NEO4J_PASSWORD must be set');
  }
  return neo4j.driver(uri, neo4j.auth.basic(user, pwd));
}

export function driver(): Driver {
  if (!g.__neo4jDriver) g.__neo4jDriver = make();
  return g.__neo4jDriver;
}

export async function readQuery<T = Record<string, unknown>>(
  cypher: string,
  params: Record<string, unknown> = {},
): Promise<T[]> {
  const s = driver().session({ defaultAccessMode: neo4j.session.READ });
  try {
    const res = await s.run(cypher, params);
    return res.records.map((r) => r.toObject() as T);
  } finally {
    await s.close();
  }
}
