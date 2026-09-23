"""Проверки пайплайна «Граф денег»: схема выгрузок, воспроизводимость, ловушки датасета."""
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moneygraph import config  # noqa: E402
from moneygraph.pipeline import run  # noqa: E402

REQUIRED = ["gid", "role", "role_score", "cluster_id", "priority_score", "evidence"]


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    out = tmp_path_factory.mktemp("out")
    summary = run(ROOT / "data", out, quiet=True)
    return out, summary


@pytest.fixture(scope="module")
def nodes_roles(result):
    return pd.read_csv(result[0] / "nodes_roles.csv")


def test_all_nodes_are_exported(nodes_roles):
    """ТЗ: строка на каждый из 2 248 узлов."""
    assert len(nodes_roles) == 2248
    assert nodes_roles.gid.nunique() == 2248


def test_required_columns_are_filled(nodes_roles):
    assert all(c in nodes_roles.columns for c in REQUIRED)
    assert nodes_roles[REQUIRED].notna().all().all()
    assert nodes_roles.role_score.between(0, 1).all()
    assert nodes_roles.priority_score.between(0, 1).all()
    assert (nodes_roles.cluster_id >= 0).all()


def test_evidence_is_human_readable_and_numeric(nodes_roles):
    """ТЗ: evidence непустой, до 200 символов и содержит числа, а не «высокий скор»."""
    assert (nodes_roles.evidence.str.len() > 0).all()
    assert (nodes_roles.evidence.str.len() <= 200).all()
    assert nodes_roles.evidence.str.contains(r"\d").all()


def test_roles_come_from_documented_dictionary(nodes_roles):
    allowed = set(config.ROLES) | {"terminal_unverified"}
    assert set(nodes_roles.role) <= allowed


def test_terminal_is_never_assigned_at_truncated_depth(nodes_roles):
    """Главная ловушка кейса: на 4-м колене обход оборван, «сток» там недоказуем."""
    assert not ((nodes_roles.role == "terminal") & (nodes_roles.depth == 4)).any()
    unverified = nodes_roles[nodes_roles.role == "terminal_unverified"]
    assert (unverified.depth == 4).all()
    assert (unverified.out_deg == 0).all()


def test_seed_nodes_are_never_classified_as_transit(nodes_roles):
    """У seed входящие занижены устройством выгрузки, коэффициент пропуска недостоверен."""
    assert not ((nodes_roles.role == "transit") & nodes_roles.is_seed).any()


def test_orphan_nodes_still_get_a_role(nodes_roles):
    orphans = nodes_roles[(nodes_roles.in_deg == 0) & (nodes_roles.out_deg == 0)]
    assert len(orphans) == 19
    assert (orphans.role == "peripheral").all()
    assert orphans.evidence.str.contains("Нет ни одного перевода").all()


def test_clusters_export(result):
    clusters = pd.read_csv(result[0] / "clusters.csv")
    nodes_roles = pd.read_csv(result[0] / "nodes_roles.csv")
    assert set(clusters.columns) >= {"cluster_id", "n_nodes", "n_seed",
                                     "sum_kzt_internal", "top_gids", "hypothesis"}
    assert clusters.n_nodes.sum() == len(nodes_roles)
    assert clusters.hypothesis.str.len().gt(0).all()
    assert set(nodes_roles.cluster_id) == set(clusters.cluster_id)


def test_top_nodes_export(result):
    top = pd.read_csv(result[0] / "top_nodes.csv")
    assert len(top) >= 20
    assert list(top["rank"]) == sorted(top["rank"])
    assert top.priority_score.is_monotonic_decreasing
    assert top.why.str.len().gt(0).all()


def test_pipeline_is_fast_enough(result):
    """ТЗ: полный пересчёт не более 5 минут."""
    assert result[1]["elapsed_sec"] < 300


def test_runs_are_byte_identical(tmp_path):
    """Воспроизводимость: одинаковый вход даёт одинаковые байты на выходе."""
    a, b = tmp_path / "a", tmp_path / "b"
    run(ROOT / "data", a, quiet=True)
    run(ROOT / "data", b, quiet=True)
    for name in ("nodes_roles.csv", "clusters.csv", "top_nodes.csv", "dashboard.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), name


def test_dashboard_identifiers_and_cluster_amounts(result):
    import json
    snapshot = json.loads((result[0] / "dashboard.json").read_text())
    nodes = snapshot["nodes"]
    ids = {n["gid"] for n in nodes}
    assert len(ids) == 2248
    original = pd.read_parquet(ROOT / "data/nodes.parquet")
    assert ids == {str(gid) for gid in original.gid}
    assert all(isinstance(n["gid"], str) for n in nodes)
    assert all(e["src"] in ids and e["dst"] in ids for e in snapshot["edges"])
    assert all(n["gid"] in ids for n in snapshot["top_nodes"])
    for cluster in snapshot["clusters"]:
        assert set(cluster["top_gids"]) <= ids
        amount = cluster["sum_kzt_internal"] / 1e6
        assert f"внутренний оборот {amount:.1f} млн KZT" in cluster["hypothesis"]


def test_cli_entry_point(tmp_path):
    """Жюри запускает одну команду — она должна работать без правок."""
    proc = subprocess.run(
        [sys.executable, "-m", "moneygraph.pipeline", "--data", str(ROOT / "data"),
         "--out", str(tmp_path), "--quiet"],
        capture_output=True, text=True, env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert proc.returncode == 0, proc.stderr
    assert (tmp_path / "nodes_roles.csv").exists()


def test_cycles_and_articulation_are_exported(nodes_roles):
    """Бонус ТЗ: возвратные потоки и структурная незаменимость."""
    assert nodes_roles.min_cycle_len.max() >= 2
    assert (nodes_roles.reciprocal_partners > 0).sum() > 0
    assert nodes_roles.is_articulation.sum() > 0
    # Цикл длины 2 — это взаимные переводы, значит у узла есть и вход, и выход.
    direct = nodes_roles[nodes_roles.reciprocal_partners > 0]
    assert (direct.in_deg > 0).all() and (direct.out_deg > 0).all()


def test_resilience_export(result):
    """Изъятие топ-N узлов должно монотонно ухудшать связность сети."""
    res = pd.read_csv(result[0] / "resilience.csv")
    assert set(res.columns) >= {"removed_top_n", "components", "largest_component",
                                "reachable_from_seeds", "reachable_share",
                                "flow_removed_kzt", "flow_removed_share"}
    assert res.removed_top_n.iloc[0] == 0
    assert res.reachable_share.iloc[0] == 1.0
    assert res.reachable_share.is_monotonic_decreasing
    assert res.largest_component.is_monotonic_decreasing
    assert res.components.is_monotonic_increasing
    # Изъятие десяти узлов из 2 248 должно отрезать заметную часть сети.
    assert res.loc[res.removed_top_n == 10, "reachable_share"].iloc[0] < 0.8
