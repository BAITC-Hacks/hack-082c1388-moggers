"""Загрузка parquet и проверки целостности до того, как строить модель."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class Dataset:
    edges: pd.DataFrame
    nodes: pd.DataFrame
    tx: pd.DataFrame

    @property
    def seeds(self) -> set[int]:
        return set(self.nodes.loc[self.nodes.is_seed, "gid"])


def load(data_dir: Path) -> Dataset:
    edges = pd.read_parquet(data_dir / "edges.parquet")
    nodes = pd.read_parquet(data_dir / "nodes.parquet")
    tx = pd.read_parquet(data_dir / "transactions.parquet")
    tx["date"] = pd.to_datetime(tx["date"])
    return Dataset(edges=edges, nodes=nodes, tx=tx)


def sanity(ds: Dataset) -> dict[str, object]:
    """Факты о датасете, которые влияют на интерпретацию ролей."""
    linked = set(ds.edges.src) | set(ds.edges.dst)
    orphans = set(ds.nodes.gid) - linked
    agg = ds.tx.groupby(["src", "dst"], as_index=False).sum_kzt.sum()
    merged = ds.edges.merge(agg, on=["src", "dst"], how="outer", indicator=True)
    return {
        "n_nodes": len(ds.nodes),
        "n_edges": len(ds.edges),
        "n_tx": len(ds.tx),
        "n_seed": int(ds.nodes.is_seed.sum()),
        "turnover_kzt": float(ds.edges.sum_kzt.sum()),
        "period": (str(ds.tx.date.min().date()), str(ds.tx.date.max().date())),
        "edges_match_tx": bool((merged._merge == "both").all()),
        "orphan_nodes": sorted(orphans),
        "orphan_seeds": sorted(orphans & ds.seeds),
    }
