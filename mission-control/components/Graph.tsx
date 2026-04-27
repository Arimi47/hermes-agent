'use client';

import dynamic from 'next/dynamic';
import { useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { colorFor, LABEL_COLOR, LABEL_ORDER } from '@/lib/labels';
import { communityColor, computeCommunities, COMMUNITY_COLORS } from '@/lib/clustering';
import DetailPanel from './DetailPanel';

// Reagraph is a WebGL graph renderer with a single GraphCanvas component
// that supports both 2D and 3D layouts via the layoutType prop. We dynamic-
// import it (ssr: false) because it touches window/document at module load.
// Replaced react-force-graph-2d/3d on 2026-04-26: the 3D variant suffered
// from WebGL context-loss black-canvas crashes on this user's hardware
// (vasturiano/3d-force-graph#194, react-three-fiber#3093).
const GraphCanvas = dynamic(
  () => import('reagraph').then((m) => m.GraphCanvas),
  { ssr: false },
) as any;

type Node = {
  id: number;
  name: string;
  label: string;
  degree: number;
};
type LinkType = 'MENTIONS' | 'REFERS_TO';
type Link = {
  source: number | Node;
  target: number | Node;
  type: LinkType;
  via: string | null;
};
type GraphData = { nodes: Node[]; links: Link[] };

// Reagraph node + edge shapes - id MUST be a string. We carry the original
// numeric id and label/degree in underscore-prefixed fields (rather than a
// nested `data` object, which appears to confuse reagraph 4.30 under load).
type RGEdge = {
  id: string;
  source: string;
  target: string;
  fill: string;
  size?: number;
};

// Reagraph passes these strings to THREE.Color, which only accepts hex / hsl /
// css-named colors and silently strips alpha from rgba(). Using rgba here
// produced 200+ "Alpha component will be ignored" warnings AND left the
// canvas blank, because the broken color values cascaded through the
// render pipeline. Hex only.
const EDGE_FILL: Record<LinkType, string> = {
  MENTIONS: '#5e5e5e',     // mid-gray, alpha simulated via theme.edge.opacity
  REFERS_TO: '#7e8a6e',    // dim sage to differentiate from prose mentions
};

const linkEnds = (l: Link): [number, number] => [
  typeof l.source === 'number' ? l.source : l.source.id,
  typeof l.target === 'number' ? l.target : l.target.id,
];

// Theme tuned to match the existing Mission Control palette: warm dark
// canvas, label-color-as-fill so per-node fills survive, dimming via
// inactiveOpacity for the "select X, dim everything else" UX.
// All color values must be hex / css-named / hsl - rgba() is parsed by
// THREE.Color which strips alpha and emits a warning per call (was 200+
// per render). Use the opacity / inactiveOpacity / selectedOpacity fields
// for transparency instead.
const HERMES_THEME = {
  canvas: {
    background: '#0a0a0a',
    fog: '#0a0a0a',
  },
  node: {
    fill: '#7A8C9E',
    activeFill: '#fb923c',
    opacity: 0.9,
    selectedOpacity: 1,
    inactiveOpacity: 0.18,
    label: {
      color: '#e6e6e6',
      stroke: '#0a0a0a',
      activeColor: '#fb923c',
    },
  },
  edge: {
    fill: '#5e5e5e',
    activeFill: '#fb923c',
    opacity: 0.55,
    selectedOpacity: 0.9,
    inactiveOpacity: 0.06,
    label: {
      color: '#888888',
      stroke: '#0a0a0a',
      activeColor: '#fb923c',
      fontSize: 6,
    },
  },
  ring: { fill: '#54616D', activeFill: '#fb923c' },
  arrow: { fill: '#474B56', activeFill: '#fb923c' },
  lasso: { border: '1px solid #fb923c', background: '#fb923c14' },
  cluster: {
    stroke: '#474B56',
    opacity: 1,
    label: { color: '#ACBAC7', stroke: '#0a0a0a' },
  },
};

export default function Graph() {
  const router = useRouter();
  const params = useSearchParams();
  const selectedId = useMemo(() => {
    const v = params.get('n');
    return v ? Number.parseInt(v, 10) : null;
  }, [params]);
  const is3D = params.get('mode') === '3d';
  const colorMode = params.get('color') === 'community' ? 'community' : 'label';

  const [data, setData] = useState<GraphData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [hover, setHover] = useState<Node | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<any>(null);

  // Force-directed layouts spread nodes to arbitrary world coordinates and
  // reagraph's default camera does NOT auto-fit to that bounding box. With
  // 433 nodes / 1272 edges the layout takes ~3-5s to settle. Try repeatedly
  // until the ref is populated and the call lands. Without this the canvas
  // appears blank because the graph is off-screen relative to the camera.
  useEffect(() => {
    if (!data) return;
    let attempts = 0;
    const tick = () => {
      if (!graphRef.current) {
        if (attempts++ < 30) setTimeout(tick, 200);
        return;
      }
      try {
        graphRef.current?.centerGraph?.();
        graphRef.current?.fitNodesInView?.();
      } catch {
        /* ref not yet wired */
      }
    };
    const t1 = setTimeout(tick, 800);
    const t2 = setTimeout(tick, 2500);
    const t3 = setTimeout(tick, 5000);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
    };
  }, [data, is3D]);

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

  // Selected node + 1-hop neighbour set, both as strings for Reagraph.
  // Used as `actives` so neighbours stay bright while the rest dims.
  const actives = useMemo(() => {
    if (selectedId == null || !data) return [] as string[];
    const s = new Set<number>([selectedId]);
    for (const l of data.links) {
      const [sid, tid] = linkEnds(l);
      if (sid === selectedId) s.add(tid);
      if (tid === selectedId) s.add(sid);
    }
    return Array.from(s).map(String);
  }, [selectedId, data]);

  const selections = useMemo(
    () => (selectedId != null ? [String(selectedId)] : []),
    [selectedId],
  );

  const rgNodes = useMemo(() => {
    if (!data) return [];
    return data.nodes.map((n) => ({
      id: String(n.id),
      label: n.name,
      size:
        n.degree >= 25 ? 14 :
        n.degree >= 12 ? 10 :
        n.degree >= 6 ? 8 : 6,
      fill:
        colorMode === 'community'
          ? communityColor(communities?.get(n.id))
          : colorFor(n.label),
      // Custom fields (consumed by event handlers via `_label`/`_degree`/
      // `_numericId`). Reagraph passes the whole node object back on click,
      // so these stay accessible without nesting under `data` (which the
      // earlier shape used and which appears to confuse reagraph 4.30's
      // node iterator under heavier loads).
      _label: n.label,
      _degree: n.degree,
      _numericId: n.id,
    }));
  }, [data, colorMode, communities]);

  const rgEdges: RGEdge[] = useMemo(() => {
    if (!data) return [];
    return data.links.map((l, i) => {
      const [sid, tid] = linkEnds(l);
      return {
        id: `e-${i}-${sid}-${tid}-${l.type}`,
        source: String(sid),
        target: String(tid),
        fill: EDGE_FILL[l.type],
      };
    });
  }, [data]);

  const setSelection = (id: number | null) => {
    const q = new URLSearchParams(params.toString());
    if (id == null) q.delete('n');
    else q.set('n', String(id));
    router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
  };

  const toggleMode = () => {
    const q = new URLSearchParams(params.toString());
    if (is3D) q.delete('mode');
    else q.set('mode', '3d');
    router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
  };

  const toggleColorMode = () => {
    const q = new URLSearchParams(params.toString());
    if (colorMode === 'community') q.delete('color');
    else q.set('color', 'community');
    router.replace(q.toString() ? `?${q.toString()}` : '/', { scroll: false });
  };

  return (
    <div className="graph-wrap" ref={wrapRef}>
      {err && <div className="graph-err">{err}</div>}
      {data && rgNodes.length > 0 && (
        // Reagraph's GraphCanvas renders an internal Three.js canvas that
        // needs a positioned parent with definite pixel dimensions to size
        // correctly. height: 100% on .graph-wrap doesn't propagate cleanly
        // through reagraph's wrapper inside a CSS grid cell, so we anchor
        // it explicitly with absolute inset:0 (the .graph-wrap is already
        // position: relative so this resolves to its bounds).
        <div style={{ position: 'absolute', inset: 0 }}>
          <GraphCanvas
            ref={graphRef}
            key={is3D ? '3d' : '2d'}
            nodes={rgNodes}
            edges={rgEdges}
            layoutType={is3D ? 'forceDirected3d' : 'forceDirected2d'}
            // Pass selections/actives only when populated. Empty arrays
            // appear to put reagraph into a "nothing-is-active" mode that
            // applies inactiveOpacity to every node.
            {...(selections.length ? { selections } : {})}
            {...(actives.length ? { actives } : {})}
            theme={HERMES_THEME}
            labelType="auto"
            cameraMode="pan"
            animated={false}
            draggable
            edgeArrowPosition="none"
            onNodeClick={(n: any) => {
              const numericId = n?._numericId ?? Number.parseInt(n?.id, 10);
              if (Number.isFinite(numericId)) setSelection(numericId);
            }}
            onCanvasClick={() => setSelection(null)}
            onNodePointerOver={(n: any) => {
              if (!n) {
                setHover(null);
                return;
              }
              setHover({
                id: n?._numericId ?? Number.parseInt(n?.id, 10),
                name: n?.label ?? '',
                label: n?._label ?? '',
                degree: n?._degree ?? 0,
              });
            }}
            onNodePointerOut={() => setHover(null)}
          />
        </div>
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
        <button className="mode-toggle" onClick={toggleMode} title="Render mode">
          <span className={`mode-segment${!is3D ? ' active' : ''}`}>2D</span>
          <span className={`mode-segment${is3D ? ' active' : ''}`}>3D</span>
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
