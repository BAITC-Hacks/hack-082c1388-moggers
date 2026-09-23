"""Один запуск: сырые parquet -> nodes_roles.csv, clusters.csv, top_nodes.csv."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from . import clusters, dashboard, features, graph, loading, priority, roles, structure, viewer
from .config import ROLES

# Округление экспорта: многопоточный scipy даёт расхождения на уровне 1e-16,
# из-за которых два одинаковых прогона давали разные байты в CSV.
EXPORT_ROUNDING = {
    "in_kzt": 2, "out_kzt": 2, "retained_kzt": 2, "flow_kzt": 2,
    "pass_through": 4, "fast_pass_share": 4,
    "pagerank": 8, "betweenness": 8, "hub": 8, "authority": 8,
}

EXPORT_COLUMNS = [
    "gid", "role", "role_score", "cluster_id", "priority_score", "evidence",
    # Дальше — признаки, на которых построены роли: любую строку можно проверить.
    "depth", "is_seed", "in_deg", "out_deg", "in_kzt", "out_kzt", "in_tx", "out_tx",
    "pass_through", "retained_kzt", "pagerank", "betweenness", "hub", "authority",
    "seed_sources", "seed_direct", "min_hops_from_seed", "clusters_bridged",
    "fast_pass_share", "max_payers_one_day", "max_receivers_one_day", "hold_days",
    "cycle_count", "min_cycle_len", "reciprocal_partners", "is_articulation",
    "depth_truncated", "flow_kzt",
]


def run(data_dir: Path, out_dir: Path, seed: int = 42, quiet: bool = False) -> dict:
    t0 = time.perf_counter()
    log = (lambda *a: None) if quiet else print

    ds = loading.load(data_dir)
    facts = loading.sanity(ds)
    log(f"Данные: {facts['n_nodes']} узлов, {facts['n_edges']} рёбер, "
        f"{facts['n_tx']} транзакций, оборот {facts['turnover_kzt']:,.0f} ₸")
    if not facts["edges_match_tx"]:
        raise SystemExit("edges и transactions не сходятся — датасет повреждён")

    g = graph.build(ds.edges, ds.nodes)
    f = features.build_features(ds, g)
    log(f"Признаки посчитаны: {f.shape[1]} колонок")

    cl = clusters.assign(g, f, seed=seed)
    f = f.merge(cl, on="gid", how="left")
    f["cluster_id"] = f.cluster_id.fillna(-1).astype(int)
    f["clusters_bridged"] = f.gid.map(
        clusters.bridged_clusters(g, dict(zip(f.gid, f.cluster_id)))).fillna(1).astype(int)
    log(f"Кластеров: {f.cluster_id.nunique()}")

    f = f.merge(roles.assign_roles(f), on="gid", how="left")
    log("Роли: " + ", ".join(f"{k}={v}" for k, v in f.role.value_counts().items()))

    f = f.merge(priority.compute(f), on="gid", how="left")

    for col, digits in EXPORT_ROUNDING.items():
        # +0.0 сводит -0.0 к 0.0: иначе знаковый ноль даёт расхождение в CSV.
        f[col] = f[col].round(digits) + 0.0

    # Округляем остальные float один раз: шум scipy иначе делает parquet
    # и HTML разными при каждом прогоне.
    for col in f.select_dtypes("float").columns:
        f[col] = f[col].round(8) + 0.0

    out_dir.mkdir(parents=True, exist_ok=True)
    # Вторичный ключ gid делает порядок строк устойчивым при равных приоритетах.
    nodes_roles = (f[EXPORT_COLUMNS]
                   .sort_values(["priority_score", "gid"], ascending=[False, True]))
    nodes_roles.to_csv(out_dir / "nodes_roles.csv", index=False)
    cluster_summary = clusters.summarize(f, ds.edges)
    cluster_summary.to_csv(out_dir / "clusters.csv", index=False)
    top = priority.top_nodes(f)
    top.to_csv(out_dir / "top_nodes.csv", index=False)

    # Что станет с сетью, если изъять топ-N: инфраструктура это была или листья.
    ranked_gids = nodes_roles.gid.tolist()
    res = structure.resilience(g, ranked_gids, ds.seeds)
    res.to_csv(out_dir / "resilience.csv", index=False)
    viewer.build(f, ds.edges, out_dir / "viewer.html", res)
    dashboard.build(nodes_roles, ds.edges, cluster_summary, top, res, facts,
                    out_dir / "dashboard.json")
    f.to_parquet(out_dir / "features.parquet", index=False)  # для интерфейса
    log(f"Устойчивость: изъятие топ-10 отрезает "
        f"{(1 - res.loc[res.removed_top_n == 10, 'reachable_share'].iloc[0]):.0%} узлов от seed")

    elapsed = time.perf_counter() - t0
    summary = {
        "elapsed_sec": round(elapsed, 2),
        "n_nodes": len(f),
        "n_clusters": int(f.cluster_id.nunique()),
        "roles": {k: int(v) for k, v in f.role.value_counts().items()},
        "nodes_in_cycles": int((f.min_cycle_len > 0).sum()),
        "reciprocal_nodes": int((f.reciprocal_partners > 0).sum()),
        "articulation_points": int(f.is_articulation.sum()),
        "facts": {k: v for k, v in facts.items() if k not in ("orphan_nodes",)},
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    log(f"Готово за {elapsed:.1f} с -> {out_dir}/  (схема сети: {out_dir}/viewer.html)")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Граф денег: пайплайн ролей и приоритетов")
    ap.add_argument("--data", default="data", type=Path)
    ap.add_argument("--out", default="out", type=Path)
    ap.add_argument("--seed", default=42, type=int, help="seed для Louvain (воспроизводимость)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    run(a.data, a.out, a.seed, a.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
