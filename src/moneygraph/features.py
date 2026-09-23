"""Признаки узлов: структура, достижимость от seed, временны́е паттерны.

Всё, на чём строятся роли, считается здесь и попадает в выгрузку —
чтобы любую роль можно было проверить по числам.
"""
from __future__ import annotations

import networkx as nx
import numpy as np
import pandas as pd

from . import structure
from .config import TRANSIT_FAST_DAYS
from .loading import Dataset


def _rank_pct(s: pd.Series) -> pd.Series:
    """Перцентиль в 0-1; устойчив к длинному хвосту нулей."""
    return s.rank(pct=True, method="max").fillna(0.0)


def structural(g: nx.DiGraph, nodes: pd.DataFrame) -> pd.DataFrame:
    df = nodes[["gid", "depth", "is_seed"]].copy()
    maps = {
        "in_deg": dict(g.in_degree()),
        "out_deg": dict(g.out_degree()),
        "in_kzt": dict(g.in_degree(weight="sum_kzt")),
        "out_kzt": dict(g.out_degree(weight="sum_kzt")),
        "in_tx": dict(g.in_degree(weight="n_tx")),
        "out_tx": dict(g.out_degree(weight="n_tx")),
    }
    for name, m in maps.items():
        df[name] = df.gid.map(m).fillna(0)
    for c in ("in_deg", "out_deg", "in_tx", "out_tx"):
        df[c] = df[c].astype(int)

    df["pagerank"] = df.gid.map(nx.pagerank(g, weight="sum_kzt")).fillna(0.0)
    # Веса-суммы нельзя подавать как длину пути, поэтому посредничество считаем
    # структурно: вопрос «кто стоит на путях», а не «через кого дороже».
    df["betweenness"] = df.gid.map(nx.betweenness_centrality(g)).fillna(0.0)
    hubs, authorities = nx.hits(g, max_iter=500, normalized=True)
    df["hub"] = df.gid.map(hubs).fillna(0.0)
    df["authority"] = df.gid.map(authorities).fillna(0.0)

    df["pass_through"] = np.where(df.in_kzt > 0, df.out_kzt / df.in_kzt.replace(0, np.nan), np.nan)
    df["retained_kzt"] = (df.in_kzt - df.out_kzt).clip(lower=0)
    df["avg_in_tx_kzt"] = np.where(df.in_tx > 0, df.in_kzt / df.in_tx.replace(0, np.nan), 0.0)
    df["avg_out_tx_kzt"] = np.where(df.out_tx > 0, df.out_kzt / df.out_tx.replace(0, np.nan), 0.0)

    # Обход шёл только по исходящим и оборвался на 4-м колене: у этих узлов
    # отсутствие исходящих — артефакт выгрузки, а не поведение.
    df["depth_truncated"] = (df.depth == 4) & (df.out_deg == 0)
    df["is_orphan"] = (df.in_deg == 0) & (df.out_deg == 0)
    return df


def seed_reachability(g: nx.DiGraph, seeds: set[int]) -> pd.DataFrame:
    """От скольких разных seed деньги доходят до узла и за сколько шагов.

    Совпадение нескольких seed на одном узле — сигнал структуры, а не совпадения.
    """
    counts: dict[int, int] = {n: 0 for n in g.nodes()}
    direct: dict[int, int] = {n: 0 for n in g.nodes()}
    min_hops: dict[int, float] = {n: np.inf for n in g.nodes()}

    for s in seeds:
        if s not in g:
            continue
        lengths = nx.single_source_shortest_path_length(g, s)
        for node, hops in lengths.items():
            if node == s:
                continue
            counts[node] += 1
            min_hops[node] = min(min_hops[node], hops)
            if hops == 1:
                direct[node] += 1

    return pd.DataFrame({
        "gid": list(g.nodes()),
        "seed_sources": [counts[n] for n in g.nodes()],
        "seed_direct": [direct[n] for n in g.nodes()],
        "min_hops_from_seed": [0 if n in seeds else min_hops[n] for n in g.nodes()],
    })


def temporal(ds: Dataset) -> pd.DataFrame:
    """Сквозной транзит, синхронный сбор и всплески — по датам транзакций."""
    tx = ds.tx
    incoming = tx.rename(columns={"dst": "gid"})[["gid", "src", "date", "sum_kzt"]]
    outgoing = tx.rename(columns={"src": "gid"})[["gid", "dst", "date", "sum_kzt"]]

    # Максимум разных плательщиков за один день — признак организованного сбора.
    payers_per_day = (incoming.groupby(["gid", "date"]).src.nunique()
                      .groupby("gid").max().rename("max_payers_one_day"))
    receivers_per_day = (outgoing.groupby(["gid", "date"]).dst.nunique()
                         .groupby("gid").max().rename("max_receivers_one_day"))

    first_in = incoming.groupby("gid").date.min().rename("first_in")
    last_out = outgoing.groupby("gid").date.max().rename("last_out")

    fast = _fast_pass_share(incoming, outgoing)
    active_days_in = incoming.groupby("gid").date.nunique().rename("active_days_in")
    active_days_out = outgoing.groupby("gid").date.nunique().rename("active_days_out")

    out = pd.concat([payers_per_day, receivers_per_day, first_in, last_out,
                     fast, active_days_in, active_days_out], axis=1)
    out.index.name = "gid"
    out = out.reset_index()
    out["hold_days"] = (out.last_out - out.first_in).dt.days
    return out.drop(columns=["first_in", "last_out"])


def _fast_pass_share(incoming: pd.DataFrame, outgoing: pd.DataFrame) -> pd.Series:
    """Доля исходящей суммы, ушедшей в пределах TRANSIT_FAST_DAYS после прихода."""
    first_in = incoming.groupby("gid").date.min()
    o = outgoing.join(first_in.rename("first_in"), on="gid")
    o = o[o.first_in.notna()]
    if o.empty:
        return pd.Series(dtype=float, name="fast_pass_share")
    gap = (o.date - o.first_in).dt.days
    o = o.assign(fast=(gap >= 0) & (gap <= TRANSIT_FAST_DAYS))
    total = o.groupby("gid").sum_kzt.sum()
    fast_sum = o[o.fast].groupby("gid").sum_kzt.sum()
    return (fast_sum / total).fillna(0.0).rename("fast_pass_share")


def build_features(ds: Dataset, g: nx.DiGraph) -> pd.DataFrame:
    df = structural(g, ds.nodes)
    df = df.merge(seed_reachability(g, ds.seeds), on="gid", how="left")
    df = df.merge(temporal(ds), on="gid", how="left")
    df = df.merge(structure.cycle_features(g), on="gid", how="left")
    df = df.merge(structure.articulation(g), on="gid", how="left")

    fill = {"seed_sources": 0, "seed_direct": 0, "max_payers_one_day": 0,
            "max_receivers_one_day": 0, "fast_pass_share": 0.0,
            "active_days_in": 0, "active_days_out": 0, "hold_days": 0,
            "cycle_count": 0, "min_cycle_len": 0, "reciprocal_partners": 0,
            "is_articulation": False}
    df = df.fillna(value=fill)
    df["min_hops_from_seed"] = df.min_hops_from_seed.replace(np.inf, -1)

    for col in ("betweenness", "pagerank", "in_kzt", "out_kzt", "seed_sources"):
        df[f"pct_{col}"] = _rank_pct(df[col])
    df["is_articulation"] = df.is_articulation.astype(bool)
    df["flow_kzt"] = df.in_kzt + df.out_kzt
    df["pct_flow_kzt"] = _rank_pct(df.flow_kzt)
    # Структурный сигнал: возврат денег отправителю плюс незаменимость в связности.
    # Цикл длины 2 — прямой возврат, он весит больше длинной петли.
    cycle_signal = np.where(df.min_cycle_len == 0, 0.0,
                            np.where(df.min_cycle_len <= 2, 1.0,
                                     np.where(df.min_cycle_len <= 4, 0.6, 0.35)))
    df["structure_score"] = np.clip(cycle_signal + 0.3 * df.is_articulation, 0, 1)
    return df
