"""Возвратные потоки и структурная незаменимость узлов.

Два сигнала, которых нет в базовых метриках:
  * деньги возвращаются отправителю — цикл в направленном графе;
  * узел держит сеть связной — точка сочленения.
"""
from __future__ import annotations

from collections import defaultdict

import networkx as nx
import pandas as pd

from .graph import undirected_projection

# Длиннее шести шагов цепочка перестаёт читаться как маршрут и взрывается в числе.
MAX_CYCLE_LEN = 6


def cycle_features(g: nx.DiGraph) -> pd.DataFrame:
    """Участие узла в циклах: сколько их и какой самый короткий.

    Цикл длины 2 — это прямой возврат денег отправителю, самый явный сигнал.
    """
    counts: dict[int, int] = defaultdict(int)
    shortest: dict[int, int] = {}
    reciprocal: dict[int, set[int]] = defaultdict(set)

    for cycle in nx.simple_cycles(g, length_bound=MAX_CYCLE_LEN):
        length = len(cycle)
        for node in cycle:
            counts[node] += 1
            if length < shortest.get(node, 99):
                shortest[node] = length
        if length == 2:
            a, b = cycle
            reciprocal[a].add(b)
            reciprocal[b].add(a)

    nodes = list(g.nodes())
    return pd.DataFrame({
        "gid": nodes,
        "cycle_count": [counts.get(n, 0) for n in nodes],
        "min_cycle_len": [shortest.get(n, 0) for n in nodes],
        "reciprocal_partners": [len(reciprocal.get(n, ())) for n in nodes],
    })


def articulation(g: nx.DiGraph) -> pd.DataFrame:
    """Точки сочленения на неориентированной проекции.

    Изъятие такого узла разрывает свою компоненту — это прямой аргумент
    в пользу проверки: связность держится на нём.
    """
    points = set(nx.articulation_points(undirected_projection(g)))
    nodes = list(g.nodes())
    return pd.DataFrame({"gid": nodes, "is_articulation": [n in points for n in nodes]})


def _reachable_from_seeds(g: nx.DiGraph, seeds: set[int]) -> set[int]:
    seen: set[int] = set()
    for s in seeds:
        if s in g:
            seen |= nx.descendants(g, s) | {s}
    return seen


def resilience(g: nx.DiGraph, ranked_gids: list[int], seeds: set[int],
               steps: tuple[int, ...] = (1, 5, 10, 20, 50)) -> pd.DataFrame:
    """Что станет с сетью, если изъять топ-N узлов приоритета.

    Главная метрика — сколько узлов остаётся достижимо от seed-клиентов:
    именно она отвечает, была ли изъята инфраструктура или только листья.
    """
    ug = undirected_projection(g)
    base_reach = len(_reachable_from_seeds(g, seeds))
    base_largest = max((len(c) for c in nx.connected_components(ug)), default=0)
    total_flow = sum(d["sum_kzt"] for _, _, d in g.edges(data=True))

    rows = [{
        "removed_top_n": 0,
        "components": nx.number_connected_components(ug),
        "largest_component": base_largest,
        "reachable_from_seeds": base_reach,
        "reachable_share": 1.0,
        "flow_removed_kzt": 0.0,
        "flow_removed_share": 0.0,
    }]

    for n in steps:
        victims = [x for x in ranked_gids[:n] if x in g]
        removed_flow = sum(d["sum_kzt"] for u, v, d in g.edges(data=True)
                           if u in set(victims) or v in set(victims))
        h = g.copy()
        h.remove_nodes_from(victims)
        uh = undirected_projection(h)
        reach = len(_reachable_from_seeds(h, seeds - set(victims)))
        rows.append({
            "removed_top_n": n,
            "components": nx.number_connected_components(uh),
            "largest_component": max((len(c) for c in nx.connected_components(uh)), default=0),
            "reachable_from_seeds": reach,
            "reachable_share": round(reach / base_reach, 4) if base_reach else 0.0,
            "flow_removed_kzt": round(removed_flow, 2),
            "flow_removed_share": round(removed_flow / total_flow, 4) if total_flow else 0.0,
        })
    return pd.DataFrame(rows)
