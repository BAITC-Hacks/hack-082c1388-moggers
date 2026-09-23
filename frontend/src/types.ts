export type Section = 'overview' | 'graph' | 'nodes' | 'clusters' | 'resilience';
export interface GraphNode {
  gid: string;
  role: string;
  role_score: number;
  cluster_id: number;
  priority_score: number;
  evidence: string;
  depth: number;
  is_seed: boolean;
  in_deg: number;
  out_deg: number;
  in_kzt: number;
  out_kzt: number;
  in_tx: number;
  out_tx: number;
  pass_through: number | null;
  seed_sources: number;
  betweenness: number;
  reciprocal_partners: number;
  min_cycle_len: number;
  is_articulation: boolean;
  depth_truncated: boolean;
  flow_kzt: number;
}
export interface Edge {
  src: string;
  dst: string;
  sum_kzt: number;
  n_tx: number;
}
export interface Cluster {
  cluster_id: number;
  n_nodes: number;
  n_seed: number;
  sum_kzt_internal: number;
  top_gids: string[];
  hypothesis: string;
}
export interface Resilience {
  removed_top_n: number;
  components: number;
  largest_component: number;
  reachable_from_seeds: number;
  reachable_share: number;
  flow_removed_kzt: number;
  flow_removed_share: number;
}
export interface Dataset {
  schema_version: number;
  summary: {
    n_nodes: number;
    n_edges: number;
    n_tx: number;
    n_seed: number;
    turnover_kzt: number;
    period: string[];
  };
  nodes: GraphNode[];
  edges: Edge[];
  clusters: Cluster[];
  top_nodes: { rank: number; gid: string; role: string; priority_score: number; why: string }[];
  resilience: Resilience[];
  role_labels: Record<string, string>;
  role_styles: Record<string, { color: string; shape: string; size: number }>;
}
export interface Route {
  section: Section;
  gid: string;
  q: string;
  role: string;
  cluster: string;
  depth: string;
  seed: string;
  scope: string;
  card: string;
  view: 'clusters' | 'node';
  focus: string;
  direction: 'all' | 'in' | 'out';
  minAmount: string;
}
