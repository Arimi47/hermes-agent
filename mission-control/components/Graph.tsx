'use client';

import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { colorFor, LABEL_COLOR, LABEL_ORDER } from '@/lib/labels';
import DetailPanel from './DetailPanel';

const ForceGraph2D = dynamic(
  () => import('react-force-graph-2d').then((m) => m.default),
  { ssr: false },
) as any;
const ForceGraph3D = dynamic(
  () => import('react-force-graph-3d').then((m) => m.default),
  { ssr: false },
) as any;

type Node = {
  id: number;
  name: string;
  label: string;
  degree: number;
  x?: number;
  y?: number;
  z?: number;
};
type LinkType = 'MENTIONS' | 'REFERS_TO';
type Link = {
  source: number | Node;
  target: number | Node;
  type: LinkType;
  via: string | null;
};
type GraphData = { nodes: Node[]; links: Link[] };

const EDGE_COLOR_BASE: Record<LinkType, string> = {
  MENTIONS: 'rgba(180, 180, 180, 0.08)',
  REFERS_TO: 'rgba(163, 177, 138, 0.18)', // sage, so YAML-derived edges feel different
};
const EDGE_COLOR_HIT: Record<LinkType, string> = {
  MENTIONS: 'rgba(251, 146, 60, 0.6)',
  REFERS_TO: 'rgba(251, 146, 60, 0.5)',
};

export default function Graph() {
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = useMemo(() => {
    const v = params.get('n');
    return v ? Number.parseInt(v, 10) : null;
  }, [params]);
  const is3D = params.get('mode') === '3d';

  const [data, setData] = useState<GraphData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [hover, setHover] = useState<Node | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const fgRef = useRef<any>(null);
  const [size, setSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 });

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const r = await fetch('/api/graph', { cache: 'no-store' });
        if (!r.ok) throw new Error(`API ${r.status}`);
        const j = (await r.json()) as GraphData;
        if (!cancelled) setData(j);
      } catch (e) {
        if (!cancelled) setErr((e as Error).message);
      }
    };
    load();
    const t = setInterval(load, 120_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, []);

  useEffect(() => {
    if (!wrapRef.current) return;
    const el = wrapRef.current;
    const ro = new ResizeObserver(() => {
      setSize({ w: el.clientWidth, h: el.clientHeight });
    });
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  const labelCounts = useMemo(() => {
    if (!data) return [] as { label: string; n: number }[];
    const m = new Map<string, number>();
    for (const n of data.nodes) m.set(n.label, (m.get(n.label) ?? 0) + 1);
    return LABEL_ORDER.filter((l) => m.has(l)).map((l) => ({
      label: l,
      n: m.get(l)!,
    }));
  }, [data]);

  const edgeCounts = useMemo(() => {
    if (!data) return { mentions: 0, refers: 0 };
    let m = 0;
    let r = 0;
    for (const l of data.links) {
      if (l.type === 'REFERS_TO') r++;
      else m++;
    }
    return { mentions: m, refers: r };
  }, [data]);

  const setSelection = useCallback(
    (id: number | null) => {
      const q = new URLSearchParams(params.toString());
      if (id == null) q.delete('n');
      else q.set('n', String(id));
      router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
    },
    [params, router],
  );

  const toggleMode = () => {
    const q = new URLSearchParams(params.toString());
    if (is3D) q.delete('mode');
    else q.set('mode', '3d');
    router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
  };

  useEffect(() => {
    if (!fgRef.current || selectedId == null || !data) return;
    const target = data.nodes.find((n) => n.id === selectedId);
    if (!target) return;
    if (is3D) {
      if (target.x == null || target.y == null || target.z == null) return;
      const dist = 80;
      const r = Math.hypot(target.x, target.y, target.z) || 1;
      fgRef.current.cameraPosition(
        {
          x: target.x * (1 + dist / r),
          y: target.y * (1 + dist / r),
          z: target.z * (1 + dist / r),
        },
        target,
        800,
      );
    } else {
      if (target.x == null || target.y == null) return;
      fgRef.current.centerAt(target.x, target.y, 600);
      fgRef.current.zoom(2.8, 600);
    }
  }, [selectedId, data, is3D]);

  const linkColor = (l: Link) => {
    const sid = typeof l.source === 'number' ? l.source : l.source.id;
    const tid = typeof l.target === 'number' ? l.target : l.target.id;
    if (selectedId != null && (sid === selectedId || tid === selectedId)) {
      return EDGE_COLOR_HIT[l.type];
    }
    return EDGE_COLOR_BASE[l.type];
  };

  const linkWidth = (l: Link) => {
    const sid = typeof l.source === 'number' ? l.source : l.source.id;
    const tid = typeof l.target === 'number' ? l.target : l.target.id;
    return selectedId != null && (sid === selectedId || tid === selectedId)
      ? 1.4
      : 0.55;
  };

  return (
    <div className="graph-wrap" ref={wrapRef}>
      {err && <div className="graph-err">{err}</div>}
      {data && size.w > 0 && !is3D && (
        <ForceGraph2D
          ref={fgRef}
          graphData={data}
          width={size.w}
          height={size.h}
          backgroundColor="#0a0a0a"
          nodeRelSize={3}
          nodeVal={(n: Node) => 1 + Math.min(n.degree, 20) * 0.5}
          nodeLabel={(n: Node) => `${n.name} · ${n.label}`}
          nodeColor={(n: Node) =>
            selectedId === n.id ? '#fb923c' : colorFor(n.label)
          }
          linkColor={linkColor}
          linkWidth={linkWidth}
          cooldownTicks={100}
          d3VelocityDecay={0.3}
          onNodeHover={(n: Node | null) => setHover(n)}
          onNodeClick={(n: Node) => setSelection(n.id)}
          onBackgroundClick={() => setSelection(null)}
          nodeCanvasObjectMode={() => 'after'}
          nodeCanvasObject={(n: Node, ctx: CanvasRenderingContext2D, scale: number) => {
            const isSelected = selectedId === n.id;
            const show = isSelected || n.degree >= 6 || scale > 2.4;
            if (!show) return;
            const r = 3 + Math.min(n.degree, 20) * 0.5;
            const fontSize = Math.max(9, 11 / scale);
            ctx.font = `${isSelected ? 600 : 400} ${fontSize}px "Space Grotesk", ui-sans-serif`;
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = isSelected
              ? 'rgba(251, 146, 60, 1)'
              : 'rgba(230, 230, 230, 0.72)';
            ctx.fillText(n.name, (n.x ?? 0) + r + 3, n.y ?? 0);
          }}
        />
      )}
      {data && size.w > 0 && is3D && (
        <ForceGraph3D
          ref={fgRef}
          graphData={data}
          width={size.w}
          height={size.h}
          backgroundColor="#0a0a0a"
          nodeRelSize={4}
          nodeVal={(n: Node) => 1 + Math.min(n.degree, 20) * 0.6}
          nodeLabel={(n: Node) => `${n.name} · ${n.label}`}
          nodeColor={(n: Node) =>
            selectedId === n.id ? '#fb923c' : colorFor(n.label)
          }
          nodeOpacity={0.85}
          linkColor={linkColor}
          linkWidth={linkWidth}
          linkOpacity={0.55}
          cooldownTicks={120}
          onNodeClick={(n: Node) => setSelection(n.id)}
          onBackgroundClick={() => setSelection(null)}
          onNodeHover={(n: Node | null) => setHover(n)}
        />
      )}
      <div className="legend">
        <div className="legend-title">Entities</div>
        {labelCounts.map(({ label, n }) => (
          <div className="legend-row" key={label}>
            <span
              className="legend-dot"
              style={{ background: LABEL_COLOR[label] ?? '#3a3a3a' }}
            />
            <span className="legend-label">{label}</span>
            <span className="legend-n">{n}</span>
          </div>
        ))}
        <div className="legend-divider" />
        <div className="legend-title">Edges</div>
        <div className="legend-row">
          <span className="legend-edge mentions" />
          <span className="legend-label">Mentions</span>
          <span className="legend-n">{edgeCounts.mentions}</span>
        </div>
        <div className="legend-row">
          <span className="legend-edge refers" />
          <span className="legend-label">Refers</span>
          <span className="legend-n">{edgeCounts.refers}</span>
        </div>
      </div>
      <button className="mode-toggle" onClick={toggleMode}>
        <span className={`mode-segment${!is3D ? ' active' : ''}`}>2D</span>
        <span className={`mode-segment${is3D ? ' active' : ''}`}>3D</span>
      </button>
      {hover && selectedId == null && (
        <div className="hover-card">
          <div className="hover-name">{hover.name}</div>
          <div className="hover-meta">
            <span
              className="hover-dot"
              style={{ background: colorFor(hover.label) }}
            />
            {hover.label} · {hover.degree} {hover.degree === 1 ? 'edge' : 'edges'}
          </div>
        </div>
      )}
      <DetailPanel
        nodeId={selectedId}
        onClose={() => setSelection(null)}
        onNavigate={(id) => setSelection(id)}
      />
    </div>
  );
}
