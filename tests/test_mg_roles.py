"""Юнит-проверки правил ролей на синтетических узлах: пороги должны работать как описано."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from moneygraph import config  # noqa: E402
from moneygraph.roles import _classify  # noqa: E402

BT_CUT, SINK_CUT = 0.002, 100_000.0


def node(**kw):
    base = dict(
        gid=1, depth=2, is_seed=False, in_deg=0, out_deg=0, in_kzt=0.0, out_kzt=0.0,
        in_tx=0, out_tx=0, pass_through=float("nan"), retained_kzt=0.0,
        avg_in_tx_kzt=0.0, avg_out_tx_kzt=0.0, pagerank=0.0, betweenness=0.0,
        hub=0.0, authority=0.0, seed_sources=0, seed_direct=0, min_hops_from_seed=2,
        clusters_bridged=1, fast_pass_share=0.0, max_payers_one_day=0,
        max_receivers_one_day=0, hold_days=0, depth_truncated=False, is_orphan=False,
        cycle_count=0, min_cycle_len=0, reciprocal_partners=0, is_articulation=False,
        structure_score=0.0,
        flow_kzt=0.0, pct_in_kzt=0.5, pct_out_kzt=0.5, cluster_id=0,
    )
    base.update(kw)
    base["flow_kzt"] = base["in_kzt"] + base["out_kzt"]
    return SimpleNamespace(**base)


def role_of(**kw):
    return _classify(node(**kw), BT_CUT, SINK_CUT)[0]


def test_consolidator_needs_collection_to_dominate():
    assert role_of(in_deg=6, out_deg=1, in_kzt=5e6, out_kzt=1e5) == "consolidator"
    # Ровно на пороге снизу — уже не консолидация.
    assert role_of(in_deg=4, out_deg=1, in_kzt=5e6, out_kzt=1e5) != "consolidator"


def test_distributor_needs_fan_out():
    assert role_of(in_deg=2, out_deg=20, in_kzt=1e6, out_kzt=5e6) == "distributor"
    assert role_of(in_deg=2, out_deg=9, in_kzt=1e6, out_kzt=5e6) != "distributor"


def test_coordinator_requires_balanced_flow_not_just_degrees():
    """Узел, раздающий кратно больше видимых входящих, — не сборщик, а точка вливания."""
    balanced = role_of(in_deg=8, out_deg=20, in_kzt=4e6, out_kzt=8e6, seed_sources=5)
    assert balanced == "coordinator"
    unbalanced = role_of(in_deg=8, out_deg=20, in_kzt=2e5, out_kzt=8e6, seed_sources=5)
    assert unbalanced == "distributor"


def test_coordinator_via_structural_position():
    assert role_of(in_deg=3, out_deg=4, in_kzt=1e6, out_kzt=1e6, betweenness=0.01,
                   seed_sources=5, clusters_bridged=4) == "coordinator"


def test_transit_window_and_seed_exclusion():
    assert role_of(in_deg=2, out_deg=2, in_kzt=1e6, out_kzt=1e6, pass_through=1.0) == "transit"
    assert role_of(in_deg=2, out_deg=2, in_kzt=1e6, out_kzt=3e5, pass_through=0.3) != "transit"
    # Для seed коэффициент пропуска недостоверен — роль не назначается.
    assert role_of(in_deg=2, out_deg=2, in_kzt=1e6, out_kzt=1e6,
                   pass_through=1.0, is_seed=True, depth=0) != "transit"


def test_terminal_only_where_traversal_did_not_stop():
    assert role_of(depth=3, in_deg=2, in_kzt=1e6, out_deg=0) == "terminal"
    truncated = role_of(depth=4, in_deg=2, in_kzt=1e6, out_deg=0, depth_truncated=True)
    assert truncated == "terminal_unverified"


def test_truncation_lowers_confidence():
    _, score_clean, _ = _classify(node(depth=2, in_deg=6, out_deg=1, in_kzt=5e6), BT_CUT, SINK_CUT)
    _, score_cut, why = _classify(
        node(depth=4, in_deg=6, out_deg=0, in_kzt=5e6, depth_truncated=True), BT_CUT, SINK_CUT)
    assert score_cut < score_clean
    assert "оборван" in why


def test_transit_confidence_scales_with_volume():
    """Одна операция у порога 5 000 ₸ не должна выглядеть как транзитная инфраструктура."""
    _, small, _ = _classify(node(in_deg=1, out_deg=1, in_kzt=5_000, out_kzt=5_000,
                                 pass_through=1.0), BT_CUT, SINK_CUT)
    _, large, _ = _classify(node(in_deg=3, out_deg=3, in_kzt=5e6, out_kzt=5e6,
                                 pass_through=1.0), BT_CUT, SINK_CUT)
    assert small < large


def test_return_flow_is_reported_first_in_evidence():
    """Возврат денег отправителю — сильнейший сигнал, он не должен теряться в обрезке."""
    _, _, why = _classify(node(in_deg=6, out_deg=1, in_kzt=5e6, reciprocal_partners=3,
                               is_articulation=True), BT_CUT, SINK_CUT)
    assert "возвращаются отправителю" in why
    assert len(why) <= 200


def test_evidence_never_exceeds_limit_with_every_extra_present():
    _, _, why = _classify(node(in_deg=9, out_deg=30, in_kzt=2e5, out_kzt=9e6,
                               betweenness=0.01, seed_sources=7, clusters_bridged=6,
                               reciprocal_partners=8, min_cycle_len=2,
                               is_articulation=True), BT_CUT, SINK_CUT)
    assert len(why) <= 200
    assert "…" not in why


@pytest.mark.parametrize("role", config.ROLES)
def test_dictionary_roles_have_russian_labels(role):
    assert config.ROLE_RU[role]
    assert role in config.ROLE_PRIORITY
