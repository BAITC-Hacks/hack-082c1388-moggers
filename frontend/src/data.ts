import type { Dataset, GraphNode, Route, Section } from './types';

export const sections: Section[] = ['overview', 'graph', 'nodes', 'clusters', 'resilience'];
export const roleOrder = [
  'coordinator',
  'consolidator',
  'distributor',
  'transit',
  'terminal',
  'terminal_unverified',
  'peripheral',
];
export const number = (value: number) =>
  new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value);
export const money = (value: number) =>
  new Intl.NumberFormat('ru-RU', { maximumFractionDigits: value >= 1e6 ? 1 : 0 }).format(
    value >= 1e6 ? value / 1e6 : value,
  ) + (value >= 1e6 ? ' млн ₸' : ' ₸');
export const percent = (value: number) =>
  new Intl.NumberFormat('ru-RU', { style: 'percent', maximumFractionDigits: 1 }).format(value);
export const score = (value: number) => value.toFixed(3);
export const rankNodes = (a: GraphNode, b: GraphNode) =>
  b.priority_score - a.priority_score || a.gid.localeCompare(b.gid);

export function readRoute(): Route {
  const [section, query = ''] = location.hash.slice(1).split('?');
  const p = new URLSearchParams(query);
  const view = p.get('view');
  const direction = p.get('direction');
  const amount = Number(p.get('minAmount'));
  return {
    section: sections.includes(section as Section) ? (section as Section) : 'overview',
    gid: p.get('gid') || '',
    card: p.get('card') === 'open' ? 'open' : '',
    q: p.get('q') || '',
    role: p.get('role') || '',
    cluster: p.get('cluster') || '',
    depth: p.get('depth') || '',
    seed: p.get('seed') || '',
    scope: ['top', 'hops1', 'hops2'].includes(p.get('scope') || '') ? p.get('scope')! : 'top',
    view: view === 'node' || view === 'clusters' ? view : p.get('gid') ? 'node' : 'clusters',
    focus: p.get('focus') || p.get('gid') || '',
    direction: direction === 'in' || direction === 'out' ? direction : 'all',
    minAmount: Number.isFinite(amount) && amount > 0 ? String(amount) : '',
  };
}
export function writeRoute(route: Route, replace = false) {
  const p = new URLSearchParams();
  for (const [key, value] of Object.entries(route)) {
    if (key !== 'section' && value && !(key === 'scope' && value === 'top')) p.set(key, value);
  }
  const hash = `#${route.section}${p.size ? '?' + p.toString() : ''}`;
  if (replace) {
    history.replaceState(null, '', hash);
    window.dispatchEvent(new HashChangeEvent('hashchange'));
  } else location.hash = hash;
}
export function filterNodes(nodes: GraphNode[], route: Route) {
  return nodes.filter(
    (n) =>
      (!route.q || n.gid.includes(route.q.trim())) &&
      (!route.role || n.role === route.role) &&
      (!route.cluster || String(n.cluster_id) === route.cluster) &&
      (!route.depth || String(n.depth) === route.depth) &&
      (!route.seed || n.is_seed === (route.seed === 'yes')),
  );
}
export function validateDataset(value: unknown): Dataset {
  const d = value as Dataset;
  if (
    !d ||
    d.schema_version !== 1 ||
    !Array.isArray(d.nodes) ||
    !Array.isArray(d.edges) ||
    !Array.isArray(d.clusters) ||
    !Array.isArray(d.top_nodes) ||
    !Array.isArray(d.resilience) ||
    !d.summary ||
    !d.role_labels ||
    !d.role_styles ||
    d.nodes.some((n) => typeof n.gid !== 'string') ||
    d.edges.some((e) => typeof e.src !== 'string' || typeof e.dst !== 'string')
  ) {
    throw new Error(
      'Сервер вернул несовместимые данные. Пересчитайте анализ и перезапустите сервер.',
    );
  }
  return d;
}
export function exportCsv(nodes: GraphNode[]) {
  const fields: (keyof GraphNode)[] = [
    'gid',
    'role',
    'role_score',
    'cluster_id',
    'priority_score',
    'evidence',
    'depth',
    'is_seed',
    'in_kzt',
    'out_kzt',
  ];
  const escape = (value: unknown) => '"' + String(value ?? '').replaceAll('"', '""') + '"';
  const csv =
    '\uFEFF' +
    [fields.join(','), ...nodes.map((n) => fields.map((f) => escape(n[f])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = 'moneygraph-nodes.csv';
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
