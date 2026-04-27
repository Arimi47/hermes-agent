'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { colorFor } from '@/lib/labels';

type Stub = { id: number; name: string; mention_count: number };
type Orphan = {
  id: number;
  name: string;
  labels: string[];
  folder: string | null;
  path: string | null;
};
type Loop = { id: number; name: string; labels: string[]; edge_type: string };
type Summary = {
  total_nodes: number;
  total_stubs: number;
  last_ingest_at: string | null;
  last_ingest_files: number;
  last_ingest_mentions: number;
  last_ingest_refers: number;
};
type LintData = {
  summary: Summary | null;
  stubs: Stub[];
  orphans: Orphan[];
  self_loops: Loop[];
  error?: string;
};

type Section = 'stubs' | 'orphans' | 'loops';

export default function LintPanel() {
  const [data, setData] = useState<LintData | null>(null);
  const [section, setSection] = useState<Section>('stubs');
  const router = useRouter();
  const params = useSearchParams();

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch('/api/lint?top=100', { cache: 'no-store' });
        const raw = (await r.json()) as Partial<LintData>;
        // Normalise: any field could be missing if the server returned
        // a partial response (e.g. an error before all queries ran).
        if (!cancelled) {
          setData({
            summary: raw.summary ?? null,
            stubs: Array.isArray(raw.stubs) ? raw.stubs : [],
            orphans: Array.isArray(raw.orphans) ? raw.orphans : [],
            self_loops: Array.isArray(raw.self_loops) ? raw.self_loops : [],
            error: raw.error,
          });
        }
      } catch (e) {
        if (!cancelled) {
          setData({
            summary: null,
            stubs: [],
            orphans: [],
            self_loops: [],
            error: (e as Error).message,
          });
        }
      }
    };
    load();
    const t = setInterval(load, 180_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  const select = (id: number) => {
    const q = new URLSearchParams(params.toString());
    q.set('n', String(id));
    router.replace(`?${q.toString()}`, { scroll: false });
  };

  const counts = useMemo(() => ({
    stubs: data?.stubs?.length ?? 0,
    orphans: data?.orphans?.length ?? 0,
    loops: data?.self_loops?.length ?? 0,
  }), [data]);

  if (!data) return <div className="activity-empty">loading lint</div>;
  if (data.error) return <div className="activity-empty">error · {data.error}</div>;
  const stubs = data.stubs ?? [];
  const orphans = data.orphans ?? [];
  const loops = data.self_loops ?? [];

  return (
    <div className="lint-panel">
      <div className="lint-summary">
        {data.summary && (
          <>
            <div className="lint-stat">
              <div className="lint-stat-label">Total nodes</div>
              <div className="lint-stat-value">{data.summary.total_nodes.toLocaleString('de-DE')}</div>
            </div>
            <div className="lint-stat">
              <div className="lint-stat-label">Stubs</div>
              <div className="lint-stat-value accent">{data.summary.total_stubs}</div>
            </div>
            <div className="lint-stat">
              <div className="lint-stat-label">Orphans</div>
              <div className="lint-stat-value">{counts.orphans}</div>
            </div>
          </>
        )}
      </div>

      <div className="lint-tabs">
        <button
          className={`lint-tab${section === 'stubs' ? ' active' : ''}`}
          onClick={() => setSection('stubs')}
          type="button"
        >
          Stubs <span className="lint-tab-n">{counts.stubs}</span>
        </button>
        <button
          className={`lint-tab${section === 'orphans' ? ' active' : ''}`}
          onClick={() => setSection('orphans')}
          type="button"
        >
          Orphans <span className="lint-tab-n">{counts.orphans}</span>
        </button>
        <button
          className={`lint-tab${section === 'loops' ? ' active' : ''}`}
          onClick={() => setSection('loops')}
          type="button"
        >
          Loops <span className="lint-tab-n">{counts.loops}</span>
        </button>
      </div>

      <div className="lint-list">
        {section === 'stubs' && stubs.length === 0 && (
          <div className="activity-empty">no unresolved stubs</div>
        )}
        {section === 'stubs' && stubs.map((s) => (
          <button
            key={s.id}
            className="lint-row"
            onClick={() => select(s.id)}
            type="button"
            title={`Mentioned ${s.mention_count} ${s.mention_count === 1 ? 'time' : 'times'} but never written as its own .md file`}
          >
            <span className="lint-pill" style={{ background: '#3a3a3a' }} />
            <span className="lint-name">{s.name}</span>
            <span className="lint-meta">{s.mention_count}×</span>
          </button>
        ))}

        {section === 'orphans' && orphans.length === 0 && (
          <div className="activity-empty">no orphan notes</div>
        )}
        {section === 'orphans' && orphans.map((o) => {
          const primary = o.labels?.find((l) => l !== 'Stub') ?? 'Note';
          return (
            <button
              key={o.id}
              className="lint-row"
              onClick={() => select(o.id)}
              type="button"
              title={`${primary} in ${o.folder ?? '(root)'} - no inbound links`}
            >
              <span
                className="lint-pill"
                style={{ background: colorFor(primary) }}
              />
              <span className="lint-name">{o.name}</span>
              <span className="lint-meta">{primary}</span>
            </button>
          );
        })}

        {section === 'loops' && loops.length === 0 && (
          <div className="activity-empty">no self-loops</div>
        )}
        {section === 'loops' && loops.map((l) => {
          const primary = l.labels?.find((x) => x !== 'Stub') ?? 'Note';
          return (
            <button
              key={`${l.id}-${l.edge_type}`}
              className="lint-row"
              onClick={() => select(l.id)}
              type="button"
              title={`${l.name} self-references via ${l.edge_type}`}
            >
              <span
                className="lint-pill"
                style={{ background: colorFor(primary) }}
              />
              <span className="lint-name">{l.name}</span>
              <span className="lint-meta">{l.edge_type.toLowerCase()}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
