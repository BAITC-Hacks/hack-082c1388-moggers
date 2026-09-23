"""Кластеризация Louvain и гипотезы о назначении кластеров.

Louvain работает на неориентированной проекции — направление теряется.
Поэтому кластеры отвечают на вопрос «кто с кем связан», а роли внутри них
считаются по направленному графу.
"""
from __future__ import annotations

import networkx as nx
import pandas as pd

from .graph import undirected_projection
from .text import count


def assign(g: nx.DiGraph, features: pd.DataFrame, seed: int = 42) -> pd.DataFrame:
    ug = undirected_projection(g)
    communities = nx.community.louvain_communities(ug, weight="weight", seed=seed)
    # Нумеруем по убыванию размера: cluster_id=0 — самое крупное сообщество.
    communities = sorted(communities, key=len, reverse=True)
    mapping = {gid: cid for cid, members in enumerate(communities) for gid in members}
    return pd.DataFrame({"gid": list(mapping), "cluster_id": list(mapping.values())})


def bridged_clusters(g: nx.DiGraph, cluster_of: dict[int, int]) -> dict[int, int]:
    """Сколько разных кластеров узел связывает своими рёбрами (включая свой)."""
    out: dict[int, int] = {}
    for n in g.nodes():
        neighbours = set(g.predecessors(n)) | set(g.successors(n))
        out[n] = len({cluster_of.get(x, -1) for x in neighbours} | {cluster_of.get(n, -1)})
    return out


def summarize(df: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    """clusters.csv: размер, число seed, внутренний оборот, топ-узлы и гипотеза."""
    cluster_of = dict(zip(df.gid, df.cluster_id))
    e = edges.assign(
        src_c=edges.src.map(cluster_of), dst_c=edges.dst.map(cluster_of)
    )
    internal = (e[e.src_c == e.dst_c].groupby("src_c").sum_kzt.sum()
                .rename("sum_kzt_internal"))

    rows = []
    for cid, part in df.groupby("cluster_id"):
        top = part.nlargest(5, "priority_score")
        rows.append({
            "cluster_id": int(cid),
            "n_nodes": len(part),
            "n_seed": int(part.is_seed.sum()),
            "sum_kzt_internal": float(internal.get(cid, 0.0)),
            "top_gids": " ".join(str(int(x)) for x in top.gid),
            "hypothesis": hypothesis(part, float(internal.get(cid, 0.0))),
        })
    return pd.DataFrame(rows).sort_values("n_nodes", ascending=False).reset_index(drop=True)


def hypothesis(part: pd.DataFrame, internal_kzt: float) -> str:
    """Гипотеза строится из состава ролей — формулируется как версия, не как вывод."""
    counts = part.role.value_counts()
    n_seed = int(part.is_seed.sum())
    coord = int(counts.get("coordinator", 0))
    cons = int(counts.get("consolidator", 0))
    dist = int(counts.get("distributor", 0))
    transit = int(counts.get("transit", 0))

    nodes_of = lambda n: count(n, "узел", "узла", "узлов")
    if coord and cons:
        kind = (f"признаки управляемой ветки: {count(coord, 'координирующий узел', 'координирующих узла', 'координирующих узлов')} "
                f"и {count(cons, 'точка консолидации', 'точки консолидации', 'точек консолидации')}")
    elif cons and dist:
        kind = (f"признаки схемы сбор-раздача: {count(cons, 'сборщик', 'сборщика', 'сборщиков')} "
                f"и {count(dist, 'распределитель', 'распределителя', 'распределителей')}")
    elif dist:
        kind = (f"признаки веерной раздачи: {count(dist, 'распределитель', 'распределителя', 'распределителей')} "
                f"на {nodes_of(len(part))}")
    elif cons:
        kind = f"признаки точки сбора: {nodes_of(cons)} аккумулируют средства"
    elif transit:
        kind = f"признаки транзитной цепочки: {nodes_of(transit)} пропускают средства дальше"
    else:
        kind = "выраженной структуры не выявлено, преимущественно периферия"

    seed_part = (count(n_seed, "seed-клиент", "seed-клиента", "seed-клиентов")
                 if n_seed else "без seed-клиентов")
    return f"{kind}; {seed_part}; внутренний оборот {internal_kzt / 1e6:.1f} млн KZT"
