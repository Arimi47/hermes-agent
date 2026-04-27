'use client';

import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { colorFor, LABEL_COLOR, LABEL_ORDER } from '@/lib/labels';
import { communityColor, computeCommunities, COMMUNITY_COLORS } from '@/lib/clustering';
import DetailPanel from './DetailPanel';

// 2D-only after a failed experiment with reagraph (4.30) and react-force-
// graph-3d. The 3D variant kept losing its WebGL context to a black canvas
// on this user's hardware (vasturiano/3d-force-graph#194); reagraph never
// rendered nodes despite the canvas mounting and the data loading, even
// after multiple integration fixes (hex colors, camera fit, removing nested
// data fields, omitting empty selections/actives, animated:false). 2D was
// always stable here - it's pure Canvas2D, no WebGL context to leak.
const ForceGraph2D = dynamic(
  () => import('react-force-graph-2d').then((m) => m.default),
  { ssr: false },
) as any;

type Node = {
  id: number;
  name: string;
  label: string;
  degree: number;
  x?: number;
  y?: number;
};
type LinkType = 'MENTIONS' | 'REFERS_TO';
type Link = {
  source: number | Node;
  target: number | Node;
  type: LinkType;
  via: string | null;
};
type GraphData = { nodes: Node[]; links: Link[] };

const EDGE_BASE: Record<LinkType, string> = {
  MENTIONS: 'rgba(180, 180, 180, 0.10)',
  REFERS_TO: 'rgba(163, 177, 138, 0.20)',
};
const EDGE_HIT: Record<LinkType, string> = {
  MENTIONS: 'rgba(251, 146, 60, 0.65)',
  REFERS_TO: 'rgba(251, 146, 60, 0.55)',
};
const EDGE_DIM: Record<LinkType, string> = {
  MENTIONS: 'rgba(180, 180, 180, 0.03)',
  REFERS_TO: 'rgba(163, 177, 138, 0.05)',
};

const linkEnds = (l: Link): [number, number] => [
  typeof l.source === 'number' ? l.source : l.source.id,
  typeof l.target === 'number' ? l.target : l.target.id,
];

export default function Graph() {
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = useMemo(() => {
    const v = params.get('n');
    return v ? Number.parseInt(v, 10) : null;
  }, [params]);
  const colorMode = params.get('color') === 'community' ? 'community' : 'label';

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

  const communities = useMemo(() => {
    if (!data) return null;
    return computeCommunities(data.nodes, data.links);
  }, [data]);

  const communityStats = useMemo(() => {
    if (!communities) return [] as { idx: number; n: number }[];
    const sizes = new Map<number, number>();
    for (const c of communities.values()) sizes.set(c, (sizes.get(c) ?? 0) + 1);
    return [...sizes.entries()]
      .sort((a, b) => a[0] - b[0])
      .slice(0, COMMUNITY_COLORS.length)
      .map(([idx, n]) => ({ idx, n }));
  }, [communities]);

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

  const neighbourSet = useMemo(() => {
    if (selectedId == null || !data) return null;
    const s = new Set<number>([selectedId]);
    for (const l of data.links) {
      const [sid, tid] = linkEnds(l);
      if (sid === selectedId) s.add(tid);
      if (tid === selectedId) s.add(sid);
    }
    return s;
  }, [selectedId, data]);

  const setSelection = useCallback(
    (id: number | null) => {
      const q = new URLSearchParams(params.toString());
      if (id == null) q.delete('n');
      else q.set('n', String(id));
      router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
    },
    [params, router],
  );

  const toggleColorMode = () => {
    const q = new URLSearchParams(params.toString());
    if (colorMode === 'community') q.delete('color');
    else q.set('color', 'community');
    router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
  };

  // Camera fly-to on selection.
  useEffect(() => {
    if (!fgRef.current || selectedId == null || !data) return;
    const target = data.nodes.find((n) => n.id === selectedId);
    if (!target || target.x == null || target.y == null) return;
    fgRef.current.centerAt(target.x, target.y, 600);
    fgRef.current.zoom(2.8, 600);
  }, [selectedId, data]);

  const linkColor = (l: Link) => {
    const [sid, tid] = linkEnds(l);
    if (neighbourSet) {
      if (sid === selectedId || tid === selectedId) return EDGE_HIT[l.type];
      return EDGE_DIM[l.type];
    }
    if (hover && (sid === hover.id || tid === hover.id)) {
      return 'rgba(251, 146, 60, 0.4)';
    }
    return EDGE_BASE[l.type];
  };

  const linkWidth = (l: Link) => {
    const [sid, tid] = linkEnds(l);
    if (neighbourSet && (sid === selectedId || tid === selectedId)) return 1.4;
    if (hover && (sid === hover.id || tid === hover.id)) return 1;
    return 0.55;
  };

  const particleCount = (l: Link) => {
    const [sid, tid] = linkEnds(l);
    const hitSelected =
      selectedId != null && (sid === selectedId || tid === selectedId);
    const hitHover = hover != null && (sid === hover.id || tid === hover.id);
    return hitSelected || hitHover ? 2 : 0;
  };

  const nodeColor = (n: Node) => {
    if (selectedId === n.id) return '#fb923c';
    const base =
      colorMode === 'community'
        ? communityColor(communities?.get(n.id))
        : colorFor(n.label);
    if (neighbourSet && !neighbourSet.has(n.id)) {
      return base.length === 7 ? base + '26' : base; // ~0.15 alpha
    }
    return base;
  };

  return (
    <div className="graph-wrap" ref={wrapRef}>
      {err && <div className="graph-err">{err}</div>}
      {data && size.w > 0 && (
        <ForceGraph2D
          ref={fgRef}
          graphData={data}
          width={size.w}
          height={size.h}
          backgroundColor="#0a0a0a"
          nodeRelSize={3}
          nodeVal={(n: Node) => 1 + Math.min(n.degree, 20) * 0.5}
          nodeLabel={(n: Node) => `${n.name} · ${n.label}`}
          nodeColor={nodeColor}
          linkColor={linkColor}
          linkWidth={linkWidth}
          linkDirectionalParticles={particleCount}
          linkDirectionalParticleWidth={0.6}
          linkDirectionalParticleSpeed={0.004}
          linkDirectionalParticleColor={() => '#fde68a'}
          cooldownTicks={100}
          d3VelocityDecay={0.3}
          onNodeHover={(n: Node | null) => setHover(n)}
          onNodeClick={(n: Node) => setSelection(n.id)}
          onBackgroundClick={() => setSelection(null)}
          nodeCanvasObjectMode={() => 'after'}
          nodeCanvasObject={(n: Node, ctx: CanvasRenderingContext2D, scale: number) => {
            const isSelected = selectedId === n.id;
            const isNeighbour = neighbourSet && neighbourSet.has(n.id);
            const show = isSelected || (isNeighbour && neighbourSet) || n.degree >= 6 || scale > 2.4;
            if (!show) return;
            const r = 3 + Math.min(n.degree, 20) * 0.5;
            const fontSize = Math.max(9, 11 / scale);
            ctx.font = `${isSelected ? 600 : 400} ${fontSize}px "Space Grotesk", ui-sans-serif`;
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';
            const alpha = neighbourSet && !isNeighbour ? 0.22 : 0.78;
            ctx.fillStyle = isSelected
              ? 'rgba(251, 146, 60, 1)'
              : `rgba(230, 230, 230, ${alpha})`;
            ctx.fillText(n.name, (n.x ?? 0) + r + 3, n.y ?? 0);
          }}
        />
      )}
      <div className="legend">
        {colorMode === 'label' ? (
          <>
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
          </>
        ) : (
          <>
            <div className="legend-title">Communities</div>
            {communityStats.map(({ idx, n }) => (
              <div className="legend-row" key={idx}>
                <span
                  className="legend-dot"
                  style={{ background: communityColor(idx) }}
                />
                <span className="legend-label">Cluster {idx + 1}</span>
                <span className="legend-n">{n}</span>
              </div>
            ))}
          </>
        )}
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
      <div className="mode-stack">
        <button className="mode-toggle" onClick={toggleColorMode} title="Colour by">
          <span className={`mode-segment${colorMode === 'label' ? ' active' : ''}`}>
            Label
          </span>
          <span className={`mode-segment${colorMode === 'community' ? ' active' : ''}`}>
            Cluster
          </span>
        </button>
      </div>
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
