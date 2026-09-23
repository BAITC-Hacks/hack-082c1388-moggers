import type { Dataset, Edge, GraphNode, Route } from './types';

export const NODE_LIMIT = 150;
export interface VisualNode {
  id: string;
  label: string;
  gid?: string;
  clusterId?: number;
  color: string;
  shape: string;
  size: number;
  seed: boolean;
  context: boolean;
  x: number;
  y: number;
}
export interface GraphModel {
  nodes: VisualNode[];
  edges: Edge[];
  total: number;
  incomingTotal: number;
  outgoingTotal: number;
}
export interface GraphIndex {
  nodes: Map<string, GraphNode>;
  incoming: Map<string, Edge[]>;
  outgoing: Map<string, Edge[]>;
  clusterEdges: Edge[];
}
const edgeOrder = (a: Edge, b: Edge) =>
  b.sum_kzt - a.sum_kzt || a.src.localeCompare(b.src) || a.dst.localeCompare(b.dst);
const slot = (i: number) => (i === 0 ? 0 : Math.ceil(i / 2) * (i % 2 ? 1 : -1));

export function indexGraph(data: Dataset): GraphIndex {
  const nodes = new Map(data.nodes.map((n) => [n.gid, n]));
  const incoming = new Map(data.nodes.map((n) => [n.gid, [] as Edge[]]));
  const outgoing = new Map(data.nodes.map((n) => [n.gid, [] as Edge[]]));
  const flows = new Map<string, Edge>();
  for (const edge of data.edges) {
    incoming.get(edge.dst)?.push(edge);
    outgoing.get(edge.src)?.push(edge);
    const src = nodes.get(edge.src)?.cluster_id,
      dst = nodes.get(edge.dst)?.cluster_id;
    if (src === undefined || dst === undefined || src === dst) continue;
    const key = `${src}>${dst}`;
    const flow = flows.get(key) || {
      src: `cluster:${src}`,
      dst: `cluster:${dst}`,
      sum_kzt: 0,
      n_tx: 0,
    };
    flow.sum_kzt += edge.sum_kzt;
    flow.n_tx += edge.n_tx;
    flows.set(key, flow);
  }
  incoming.forEach((edges) => edges.sort(edgeOrder));
  outgoing.forEach((edges) => edges.sort(edgeOrder));
  return {
    nodes,
    incoming,
    outgoing,
    clusterEdges: [...flows.values()]
      .map((e) => ({ ...e, sum_kzt: Math.round(e.sum_kzt * 100) / 100 }))
      .sort(edgeOrder),
  };
}

export function clusterGraph(
  data: Dataset,
  index: GraphIndex,
  count: number,
  selected = '',
): GraphModel {
  const sorted = [...data.clusters].sort(
    (a, b) => b.n_nodes - a.n_nodes || a.cluster_id - b.cluster_id,
  );
  const clusters = sorted.slice(0, count);
  const requested = sorted.find((c) => String(c.cluster_id) === selected);
  if (requested && !clusters.includes(requested)) {
    clusters.pop();
    clusters.push(requested);
  }
  const nodes: VisualNode[] = clusters.map((c) => {
    const rank = sorted.indexOf(c);
    return {
      id: `cluster:${c.cluster_id}`,
      clusterId: c.cluster_id,
      label: `Кластер ${c.cluster_id}\n${c.n_nodes} участников · ${c.n_seed} seed`,
      color: c.n_seed > 1 ? '#2563eb' : '#7b98be',
      shape: 'round-rectangle',
      size: 38 + Math.min(Math.sqrt(c.n_nodes) * 2, 36),
      seed: c.n_seed > 0,
      context: false,
      x: (rank % 4) * 240,
      y: Math.floor(rank / 4) * 160,
    };
  });
  const ids = new Set(nodes.map((n) => n.id));
  return {
    nodes,
    edges: index.clusterEdges.filter((e) => ids.has(e.src) && ids.has(e.dst)),
    total: sorted.length,
    incomingTotal: 0,
    outgoingTotal: 0,
  };
}

export function nodeGraph(
  data: Dataset,
  index: GraphIndex,
  filtered: GraphNode[],
  route: Route,
  inLimit = 10,
  outLimit = 10,
  expanded: string[] = [],
): GraphModel {
  const focus = route.focus || route.gid;
  const anchor = index.nodes.get(focus);
  if (!anchor) return { nodes: [], edges: [], total: 0, incomingTotal: 0, outgoingTotal: 0 };
  const matches = new Set(filtered.map((n) => n.gid));
  const minimum = Math.max(Number(route.minAmount) || 0, 0);
  const allowed = (gid: string) => gid === focus || matches.has(gid);
  const incoming = (gid: string) =>
    route.direction === 'out'
      ? []
      : (index.incoming.get(gid) || []).filter(
          (e) => e.sum_kzt >= minimum && allowed(e.src) && e.src !== gid,
        );
  const outgoing = (gid: string) =>
    route.direction === 'in'
      ? []
      : (index.outgoing.get(gid) || []).filter(
          (e) => e.sum_kzt >= minimum && allowed(e.dst) && e.dst !== gid,
        );
  const ins = incoming(focus),
    outs = outgoing(focus);
  const payers = new Set(ins.map((e) => e.src)),
    receivers = new Set(outs.map((e) => e.dst));
  const positions = new Map<string, { lane: number; x: number; y: number }>();
  positions.set(focus, { lane: 0, x: 0, y: 0 });
  const laneCounts = new Map<number, number>();
  const candidates = new Set([focus, ...payers, ...receivers]);
  const chosenEdges = new Map<string, Edge>();
  function add(gid: string, lane: number) {
    if (positions.has(gid) || positions.size >= NODE_LIMIT) return;
    const position = laneCounts.get(lane) || 0;
    laneCounts.set(lane, position + 1);
    positions.set(gid, {
      lane,
      x: lane * 340,
      y: lane === 0 ? -150 - position * 70 : slot(position) * 65,
    });
  }
  ins.slice(0, inLimit).forEach((e) => add(e.src, receivers.has(e.src) ? 0 : -1));
  outs.slice(0, outLimit).forEach((e) => add(e.dst, payers.has(e.dst) ? 0 : 1));
  function connect(gid: string, grow: boolean) {
    const parent = positions.get(gid);
    if (!parent) return;
    const left = incoming(gid),
      right = outgoing(gid);
    left.forEach((e) => candidates.add(e.src));
    right.forEach((e) => candidates.add(e.dst));
    if (grow) {
      left.slice(0, 10).forEach((e) => add(e.src, parent.lane - 1));
      right.slice(0, 10).forEach((e) => add(e.dst, parent.lane + 1));
    }
    for (const e of [...left, ...right]) {
      if (positions.has(e.src) && positions.has(e.dst)) chosenEdges.set(`${e.src}>${e.dst}`, e);
    }
  }
  connect(focus, false);
  const anchors = route.scope === 'hops2' ? [...positions.keys()].filter((id) => id !== focus) : [];
  for (const gid of [...new Set([...anchors, ...expanded])]) connect(gid, true);
  // Include every allowed edge between visible nodes, with direction filtering
  // relative to the focus/explicitly expanded anchors, not arbitrary graph paths.
  for (const gid of [focus, ...anchors, ...expanded]) connect(gid, false);
  for (const e of index.outgoing.get(focus) || []) {
    if (e.dst === focus && e.sum_kzt >= minimum) chosenEdges.set(`${focus}>${focus}`, e);
  }
  const nodes: VisualNode[] = [...positions].map(([gid, position]) => {
    const n = index.nodes.get(gid)!;
    const style = data.role_styles[n.role];
    return {
      id: gid,
      gid,
      label: gid === focus ? gid : `…${gid.slice(-8)}`,
      color: style.color,
      shape: style.shape,
      size: gid === focus ? 52 : Math.max(style.size, 27),
      seed: n.is_seed,
      context: !matches.has(gid),
      x: position.x,
      y: position.y,
    };
  });
  return {
    nodes,
    edges: [...chosenEdges.values()].sort(edgeOrder),
    total: candidates.size,
    incomingTotal: ins.length,
    outgoingTotal: outs.length,
  };
}
