"""Cluster turnover must count internal edges once and exclude external flows."""
import pandas as pd

from moneygraph.clusters import summarize


def test_hypothesis_uses_internal_edges_not_total_node_turnover():
    nodes = pd.DataFrame([
        {"gid": 1, "cluster_id": 0, "is_seed": True, "role": "transit",
         "priority_score": 0.9, "flow_kzt": 9_000_000},
        {"gid": 2, "cluster_id": 0, "is_seed": False, "role": "terminal",
         "priority_score": 0.8, "flow_kzt": 4_000_000},
        {"gid": 3, "cluster_id": 1, "is_seed": False, "role": "peripheral",
         "priority_score": 0.1, "flow_kzt": 8_000_000},
    ])
    edges = pd.DataFrame([
        {"src": 1, "dst": 2, "sum_kzt": 2_000_000},
        {"src": 2, "dst": 1, "sum_kzt": 1_000_000},
        {"src": 1, "dst": 3, "sum_kzt": 8_000_000},
    ])
    result = summarize(nodes, edges).set_index("cluster_id")
    assert result.loc[0, "sum_kzt_internal"] == 3_000_000
    assert "внутренний оборот 3.0 млн KZT" in result.loc[0, "hypothesis"]
    assert result.loc[1, "sum_kzt_internal"] == 0
    assert "внутренний оборот 0.0 млн KZT" in result.loc[1, "hypothesis"]
