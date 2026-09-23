"""Deterministic, lossless snapshot for the analyst web application."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .viewer import ROLE_RU_FULL, ROLE_STYLE


def records(frame: pd.DataFrame, identifiers: tuple[str, ...] = ()) -> list[dict]:
    frame = frame.copy()
    for column in identifiers:
        frame[column] = frame[column].map(lambda value: str(int(value)))
    # pandas maps missing and non-finite values to JSON null without losing gid.
    return json.loads(frame.to_json(orient="records", double_precision=10))


def build(nodes: pd.DataFrame, edges: pd.DataFrame, clusters: pd.DataFrame,
          top: pd.DataFrame, resilience: pd.DataFrame, facts: dict,
          out_path: Path) -> None:
    cluster_rows = records(clusters.sort_values("cluster_id"))
    for row in cluster_rows:
        row["top_gids"] = row["top_gids"].split()
    summary = {key: value for key, value in facts.items()
               if key not in {"orphan_nodes", "orphan_seeds"}}
    payload = {
        "schema_version": 1,
        "summary": summary,
        "nodes": records(nodes.sort_values(["priority_score", "gid"],
                                          ascending=[False, True]), ("gid",)),
        "edges": records(edges[["src", "dst", "sum_kzt", "n_tx"]]
                         .sort_values(["src", "dst"]), ("src", "dst")),
        "clusters": cluster_rows,
        "top_nodes": records(top.sort_values("rank"), ("gid",)),
        "resilience": records(resilience.sort_values("removed_top_n")),
        "role_labels": ROLE_RU_FULL,
        "role_styles": ROLE_STYLE,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False,
                                   sort_keys=True, separators=(",", ":")), encoding="utf-8")
