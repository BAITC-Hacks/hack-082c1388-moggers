"""Инструменты агента: запросы к посчитанному графу.

Все числа берутся отсюда. Модель ничего не вычисляет сама — она только
выбирает инструмент, читает его JSON и формулирует ответ.
Каждый инструмент возвращает gid, на которые можно сослаться в ответе.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from ..config import ROLE_RU
from ..graph import build, undirected_projection
from ..loading import load

MAX_ROWS = 25          # сколько строк отдаём модели: больше она всё равно не удержит
MAX_PATH_LEN = 5       # длиннее цепочка перестаёт читаться как маршрут


def _money(x: float) -> str:
    return f"{x / 1e6:.2f} млн ₸" if x >= 1e6 else f"{x / 1e3:.0f} тыс ₸"


@dataclass
class GraphContext:
    """Граф и посчитанные признаки. Собирается один раз на сессию."""

    g: nx.DiGraph
    features: pd.DataFrame
    seeds: set[int]

    @classmethod
    def from_dirs(cls, data_dir: Path, out_dir: Path) -> "GraphContext":
        features_path = out_dir / "features.parquet"
        if not features_path.exists():
            raise FileNotFoundError(
                f"{features_path} не найден — сначала запустите ./run.sh")
        ds = load(data_dir)
        return cls(g=build(ds.edges, ds.nodes),
                   features=pd.read_parquet(features_path), seeds=ds.seeds)

    def row(self, gid: int) -> pd.Series | None:
        hit = self.features[self.features.gid == gid]
        return None if hit.empty else hit.iloc[0]

    @property
    def known_gids(self) -> set[int]:
        return set(self.features.gid)


def _brief(ctx: GraphContext, gid: int) -> dict[str, Any]:
    """Короткая карточка узла — то, что нужно для ссылки в ответе."""
    r = ctx.row(gid)
    if r is None:
        return {"gid": gid, "error": "узла нет в выгрузке"}
    return {
        "gid": int(r.gid),
        "role": r.role,
        "role_ru": ROLE_RU.get(r.role, r.role),
        "priority_score": round(float(r.priority_score), 4),
        "cluster_id": int(r.cluster_id),
        "depth": int(r.depth),
        "is_seed": bool(r.is_seed),
        "in_deg": int(r.in_deg),
        "out_deg": int(r.out_deg),
        "in_kzt": round(float(r.in_kzt), 2),
        "out_kzt": round(float(r.out_kzt), 2),
        "evidence": r.evidence,
    }


# ---------------------------------------------------------------- инструменты

def node_profile(ctx: GraphContext, gid: int) -> dict[str, Any]:
    """Полный профиль узла: роль, обоснование, метрики, структурные признаки."""
    r = ctx.row(gid)
    if r is None:
        return {"error": f"узла {gid} нет в выгрузке"}
    out = _brief(ctx, gid)
    out.update({
        "role_score": round(float(r.role_score), 3),
        "pass_through": None if pd.isna(r.pass_through) else round(float(r.pass_through), 3),
        "seed_sources": int(r.seed_sources),
        "seed_direct": int(r.seed_direct),
        "betweenness": round(float(r.betweenness), 6),
        "pagerank": round(float(r.pagerank), 6),
        "reciprocal_partners": int(r.reciprocal_partners),
        "min_cycle_len": int(r.min_cycle_len),
        "is_articulation": bool(r.is_articulation),
        "depth_truncated": bool(r.depth_truncated),
        "max_payers_one_day": int(r.max_payers_one_day),
        "fast_pass_share": round(float(r.fast_pass_share), 3),
    })
    return out


def find_nodes(ctx: GraphContext, role: str | None = None, cluster_id: int | None = None,
               min_priority: float | None = None, is_seed: bool | None = None,
               limit: int = 10) -> dict[str, Any]:
    """Поиск узлов по роли, кластеру, приоритету. Отсортировано по приоритету."""
    df = ctx.features
    if role:
        df = df[df.role == role]
    if cluster_id is not None:
        df = df[df.cluster_id == cluster_id]
    if min_priority is not None:
        df = df[df.priority_score >= min_priority]
    if is_seed is not None:
        df = df[df.is_seed == is_seed]
    df = df.nlargest(min(limit, MAX_ROWS), "priority_score")
    return {"found": len(df), "nodes": [_brief(ctx, int(g)) for g in df.gid]}


def convergence(ctx: GraphContext, gids: list[int], max_hops: int = 4,
                min_sources: int = 2) -> dict[str, Any]:
    """Куда сходятся деньги нескольких счетов — главный вопрос аналитика.

    Отвечает на «кто собирает деньги с этих пятерых»: ищет узлы, достижимые
    по переводам от нескольких исходных счетов сразу.
    """
    known = [g for g in gids if g in ctx.g]
    missing = [g for g in gids if g not in ctx.g]
    hits: Counter[int] = Counter()
    for src in known:
        reached = nx.single_source_shortest_path_length(ctx.g, src, cutoff=max_hops)
        for node in reached:
            if node != src:
                hits[node] += 1

    common = [(n, c) for n, c in hits.items() if c >= min_sources and n not in set(known)]
    common.sort(key=lambda x: (-x[1], -float(ctx.row(x[0]).priority_score
                                             if ctx.row(x[0]) is not None else 0)))
    nodes = []
    for node, count in common[:MAX_ROWS]:
        item = _brief(ctx, node)
        item["reached_from_n_sources"] = count
        nodes.append(item)

    return {
        "queried": known,
        "not_in_graph": missing,
        "max_hops": max_hops,
        "converging_nodes": len(common),
        "nodes": nodes,
        "note": ("Ни один узел не собирает средства более чем от одного из указанных счетов "
                 "в пределах заданного числа колен — общей точки сбора у них не видно."
                 if not common else ""),
    }


def trace_money(ctx: GraphContext, src: int, dst: int, max_len: int = MAX_PATH_LEN) -> dict[str, Any]:
    """Маршруты денег от одного счёта к другому с суммами на каждом шаге."""
    if src not in ctx.g or dst not in ctx.g:
        return {"error": "один из узлов отсутствует в графе", "src": src, "dst": dst}
    if not nx.has_path(ctx.g, src, dst):
        return {"src": src, "dst": dst, "paths": [],
                "note": "Переводов по этому направлению в выгрузке нет."}

    paths = []
    for path in nx.all_simple_paths(ctx.g, src, dst, cutoff=max_len):
        steps = [{"from": int(path[i]), "to": int(path[i + 1]),
                  "sum_kzt": round(ctx.g[path[i]][path[i + 1]]["sum_kzt"], 2),
                  "n_tx": int(ctx.g[path[i]][path[i + 1]]["n_tx"])}
                 for i in range(len(path) - 1)]
        paths.append({"length": len(path) - 1,
                      "bottleneck_kzt": round(min(s["sum_kzt"] for s in steps), 2),
                      "steps": steps})
        if len(paths) >= 10:
            break
    paths.sort(key=lambda p: (p["length"], -p["bottleneck_kzt"]))
    return {"src": src, "dst": dst, "paths_found": len(paths), "paths": paths[:5]}


def counterparties(ctx: GraphContext, gid: int, direction: str = "both",
                   limit: int = 10) -> dict[str, Any]:
    """Кто платит узлу и кому платит он — по убыванию сумм."""
    if gid not in ctx.g:
        return {"error": f"узла {gid} нет в графе"}
    limit = min(limit, MAX_ROWS)
    out: dict[str, Any] = {"gid": gid}
    if direction in ("in", "both"):
        rows = sorted(((u, d["sum_kzt"], d["n_tx"]) for u, _, d in ctx.g.in_edges(gid, data=True)),
                      key=lambda x: -x[1])[:limit]
        out["payers"] = [{**_brief(ctx, int(u)), "sum_kzt": round(s, 2), "n_tx": n}
                         for u, s, n in rows]
    if direction in ("out", "both"):
        rows = sorted(((v, d["sum_kzt"], d["n_tx"]) for _, v, d in ctx.g.out_edges(gid, data=True)),
                      key=lambda x: -x[1])[:limit]
        out["receivers"] = [{**_brief(ctx, int(v)), "sum_kzt": round(s, 2), "n_tx": n}
                            for v, s, n in rows]
    return out


def cluster_profile(ctx: GraphContext, cluster_id: int) -> dict[str, Any]:
    """Состав кластера: роли, seed, оборот, ключевые узлы."""
    part = ctx.features[ctx.features.cluster_id == cluster_id]
    if part.empty:
        return {"error": f"кластера {cluster_id} нет"}
    return {
        "cluster_id": cluster_id,
        "n_nodes": len(part),
        "n_seed": int(part.is_seed.sum()),
        "roles": {k: int(v) for k, v in part.role.value_counts().items()},
        "total_flow_kzt": round(float(part.flow_kzt.sum()), 2),
        "top_nodes": [_brief(ctx, int(g)) for g in part.nlargest(5, "priority_score").gid],
    }


def removal_impact(ctx: GraphContext, gids: list[int]) -> dict[str, Any]:
    """Что станет с сетью, если изъять указанные узлы.

    Главная метрика — сколько узлов остаётся достижимо от seed-клиентов.
    """
    victims = [g for g in gids if g in ctx.g]
    if not victims:
        return {"error": "ни один из указанных узлов не найден в графе"}

    def reachable(graph: nx.DiGraph, seeds: set[int]) -> int:
        seen: set[int] = set()
        for s in seeds:
            if s in graph:
                seen |= nx.descendants(graph, s) | {s}
        return len(seen)

    before_reach = reachable(ctx.g, ctx.seeds)
    before_components = nx.number_connected_components(undirected_projection(ctx.g))
    flow_removed = sum(d["sum_kzt"] for u, v, d in ctx.g.edges(data=True)
                       if u in set(victims) or v in set(victims))

    h = ctx.g.copy()
    h.remove_nodes_from(victims)
    after_reach = reachable(h, ctx.seeds - set(victims))
    after_components = nx.number_connected_components(undirected_projection(h))

    return {
        "removed": victims,
        "reachable_from_seeds_before": before_reach,
        "reachable_from_seeds_after": after_reach,
        "share_cut_off": round(1 - after_reach / before_reach, 4) if before_reach else 0.0,
        "components_before": before_components,
        "components_after": after_components,
        "flow_removed_kzt": round(flow_removed, 2),
        "flow_removed_readable": _money(flow_removed),
    }


def return_flows(ctx: GraphContext, gid: int) -> dict[str, Any]:
    """Возвращаются ли деньги к отправителю: встречные переводы и замкнутые цепочки."""
    r = ctx.row(gid)
    if r is None:
        return {"error": f"узла {gid} нет в выгрузке"}
    partners = []
    if gid in ctx.g:
        for v in ctx.g.successors(gid):
            if ctx.g.has_edge(v, gid):
                partners.append({
                    "gid": int(v),
                    "sent_kzt": round(ctx.g[gid][v]["sum_kzt"], 2),
                    "received_back_kzt": round(ctx.g[v][gid]["sum_kzt"], 2),
                })
    return {
        "gid": gid,
        "reciprocal_partners": int(r.reciprocal_partners),
        "min_cycle_len": int(r.min_cycle_len),
        "pairs": sorted(partners, key=lambda p: -p["sent_kzt"])[:MAX_ROWS],
    }


def data_gaps(ctx: GraphContext, gid: int) -> dict[str, Any]:
    """Чего нельзя утверждать об узле по этим данным и что запросить дальше.

    Прямо отвечает на бонусный пункт ТЗ про оценку полноты.
    """
    r = ctx.row(gid)
    if r is None:
        return {"error": f"узла {gid} нет в выгрузке"}
    gaps, asks = [], []

    if bool(r.depth_truncated):
        gaps.append("Узел на 4-м колене: обход остановлен здесь, исходящие переводы "
                    "могли не попасть в выгрузку.")
        asks.append("Запросить выгрузку на 5-е колено от этого узла.")
    if bool(r.is_seed):
        gaps.append("Это seed-клиент: граф собран от него по исходящим, поэтому "
                    "входящие суммы занижены и коэффициент пропуска недостоверен.")
        asks.append("Запросить входящие переводы на этот счёт за период.")
    if float(r.in_kzt) > 0 and float(r.out_kzt) > 3 * float(r.in_kzt) and float(r.out_kzt) > 1e6:
        gaps.append(f"Исходящие ({_money(float(r.out_kzt))}) кратно превышают видимые "
                    f"входящие ({_money(float(r.in_kzt))}): источник средств вне выгрузки.")
        asks.append("Запросить входящие переводы, включая межбанковские и внесение наличных.")
    if int(r.in_deg) == 0 and int(r.out_deg) == 0:
        gaps.append("У узла нет ни одного перевода в выгрузке: операции либо ниже "
                    "порога 5 000 ₸, либо вне периметра.")
        asks.append("Запросить операции ниже порога 5 000 ₸.")

    gaps.append("В данных нет атрибутов клиента, типов операций и остатков — "
                "оценка построена только на структуре переводов и суммах.")
    return {"gid": gid, "gaps": gaps, "suggested_requests": asks}


TOOLS = {
    "node_profile": node_profile,
    "find_nodes": find_nodes,
    "convergence": convergence,
    "trace_money": trace_money,
    "counterparties": counterparties,
    "cluster_profile": cluster_profile,
    "removal_impact": removal_impact,
    "return_flows": return_flows,
    "data_gaps": data_gaps,
}
