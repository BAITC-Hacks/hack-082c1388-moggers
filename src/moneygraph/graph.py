"""Направленный взвешенный граф переводов."""
from __future__ import annotations

import networkx as nx
import pandas as pd


def build(edges: pd.DataFrame, nodes: pd.DataFrame) -> nx.DiGraph:
    """Узлы добавляются все, включая 19 seed без единого ребра."""
    g = nx.DiGraph()
    g.add_nodes_from(nodes.gid.tolist())
    for r in edges.itertuples(index=False):
        g.add_edge(int(r.src), int(r.dst),
                   sum_kzt=float(r.sum_kzt), n_tx=int(r.n_tx), depth=int(r.depth))
    nx.set_node_attributes(g, dict(zip(nodes.gid, nodes.depth)), "depth")
    nx.set_node_attributes(g, dict(zip(nodes.gid, nodes.is_seed)), "is_seed")
    return g


def undirected_projection(g: nx.DiGraph) -> nx.Graph:
    """Для кластеризации: Louvain работает только на неориентированном графе.

    Направление при этом теряется — оговорено в README, роли считаются по DiGraph.
    """
    ug = nx.Graph()
    ug.add_nodes_from(g.nodes())
    for u, v, data in g.edges(data=True):
        w = data["sum_kzt"]
        if ug.has_edge(u, v):
            ug[u][v]["weight"] += w
        else:
            ug.add_edge(u, v, weight=w)
    return ug
