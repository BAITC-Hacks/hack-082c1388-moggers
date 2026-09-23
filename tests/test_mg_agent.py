"""Проверки AI-ассистента: инструменты, разбор намерения, валидация ссылок, LLM-ветка."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from moneygraph.agent import llm, tools  # noqa: E402
from moneygraph.agent.session import Assistant  # noqa: E402
from moneygraph.agent.validator import is_grounded, mentioned_gids, validate  # noqa: E402
from moneygraph.pipeline import run  # noqa: E402


@pytest.fixture(scope="module")
def out_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("agent_out")
    run(ROOT / "data", out, quiet=True)
    return out


@pytest.fixture(scope="module")
def assistant(out_dir):
    return Assistant(ROOT / "data", out_dir)


@pytest.fixture(scope="module")
def top_gids(assistant):
    return [int(g) for g in assistant.ctx.features.nlargest(4, "priority_score").gid]


# ---------------------------------------------------------------- инструменты

def test_node_profile_returns_evidence(assistant, top_gids):
    p = tools.node_profile(assistant.ctx, top_gids[0])
    assert p["gid"] == top_gids[0]
    assert p["evidence"] and any(ch.isdigit() for ch in p["evidence"])
    assert 0 <= p["priority_score"] <= 1


def test_unknown_gid_is_reported_not_invented(assistant):
    assert "error" in tools.node_profile(assistant.ctx, 999999999999999999)
    assert "error" in tools.counterparties(assistant.ctx, 999999999999999999)


def test_convergence_finds_shared_collectors(assistant, top_gids):
    """Главный вопрос ТЗ: кто собирает деньги с нескольких счетов."""
    r = tools.convergence(assistant.ctx, top_gids[:2], max_hops=4)
    assert r["queried"] == top_gids[:2]
    for node in r["nodes"]:
        assert node["reached_from_n_sources"] >= 2
        assert node["gid"] not in top_gids[:2]


def test_convergence_says_so_when_nothing_converges(assistant):
    """Сеть не монолитна: отсутствие общей точки — это тоже ответ, а не пустота."""
    isolated = assistant.ctx.features[
        (assistant.ctx.features.in_deg == 0) & (assistant.ctx.features.out_deg == 0)]
    r = tools.convergence(assistant.ctx, [int(g) for g in isolated.gid[:3]])
    assert r["nodes"] == []
    assert r["note"]


def test_trace_money_returns_steps_with_amounts(assistant):
    edges = list(assistant.ctx.g.edges())[:1]
    src, dst = edges[0]
    r = tools.trace_money(assistant.ctx, int(src), int(dst))
    assert r["paths_found"] >= 1
    assert all(s["sum_kzt"] > 0 for s in r["paths"][0]["steps"])


def test_removal_impact_matches_pipeline_resilience(assistant, out_dir, top_gids):
    """Инструмент и выгрузка не должны расходиться в числах."""
    import pandas as pd
    res = pd.read_csv(out_dir / "resilience.csv")
    expected = res.loc[res.removed_top_n == 1, "reachable_share"].iloc[0]
    r = tools.removal_impact(assistant.ctx, top_gids[:1])
    assert r["share_cut_off"] == pytest.approx(1 - expected, abs=1e-3)


def test_data_gaps_names_a_next_request(assistant):
    truncated = assistant.ctx.features[assistant.ctx.features.depth_truncated]
    r = tools.data_gaps(assistant.ctx, int(truncated.iloc[0].gid))
    assert any("5-е колено" in a for a in r["suggested_requests"])
    assert r["gaps"]


# ---------------------------------------------------------------- валидатор

def test_validator_drops_invented_gids():
    known = {100000003684369100}
    text = ("Узел [100000003684369100] собирает средства. "
            "Далее деньги уходят на [100000000000000001]. Конец.")
    clean, warnings = validate(text, known)
    assert "100000000000000001" not in clean
    assert "100000003684369100" in clean
    assert len(warnings) == 1


def test_grounding_requires_real_references():
    known = {100000003684369100}
    assert is_grounded("Смотри [100000003684369100].", known)
    assert not is_grounded("Это точно организатор.", known)
    assert mentioned_gids("нет чисел") == set()


# ---------------------------------------------------------------- режим без LLM

@pytest.mark.parametrize("question,expected_tool", [
    ("почему у {0} такая роль?", "node_profile"),
    ("кто собирает деньги с {0} и {1}?", "convergence"),
    ("какой путь от {0} к {1}?", "trace_money"),
    ("что будет если убрать {0}?", "removal_impact"),
    ("есть ли возвраты у {0}?", "return_flows"),
    ("каких данных не хватает по {0}?", "data_gaps"),
    ("кто платит узлу {0}?", "counterparties"),
    ("покажи координаторов", "find_nodes"),
    ("что в кластере 3?", "cluster_profile"),
])
def test_offline_routing(assistant, top_gids, question, expected_tool):
    q = question.format(*top_gids)
    tool, _ = assistant._route(q)
    assert tool == expected_tool


def test_offline_answer_is_grounded(assistant, top_gids):
    r = assistant.ask(f"почему у {top_gids[0]} такая роль?", use_llm=False)
    assert not r.llm_used
    assert is_grounded(r.text, assistant.ctx.known_gids)


# ---------------------------------------------------------------- LLM-ветка (мок)

def test_llm_path_uses_tools_and_validates(assistant, top_gids, monkeypatch):
    monkeypatch.setattr(llm, "in_scope", lambda *args: True)
    called: list[str] = []

    def fake_run(messages, dispatch, on_step=None, max_steps=6):
        dispatch("node_profile", {"gid": top_gids[0]})
        if on_step:
            on_step("node_profile", {})
        called.append("ok")
        return f"Узел [{top_gids[0]}] показывает признаки координации."

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "run", fake_run)
    r = assistant.ask("кто главный?", use_llm=True)
    assert r.llm_used and called
    assert str(top_gids[0]) in r.text
    assert not r.warnings


def test_hallucinated_answer_falls_back(assistant, monkeypatch):
    monkeypatch.setattr(llm, "in_scope", lambda *args: True)
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "run", lambda *a, **k: "Деньги ушли на [100000000000000009].")
    r = assistant.ask("кого смотреть первым?", use_llm=True)
    assert "100000000000000009" not in r.text
    assert any("не прошёл проверку" in w for w in r.warnings)


def test_llm_outage_still_answers(assistant, monkeypatch):
    monkeypatch.setattr(llm, "in_scope", lambda *args: True)
    def boom(*a, **k):
        raise RuntimeError("503 upstream")

    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "run", boom)
    r = assistant.ask("покажи координаторов", use_llm=True)
    assert r.text and not r.llm_used
    assert any("LLM недоступен" in w for w in r.warnings)


def test_tool_specs_match_implementations():
    names = {spec["function"]["name"] for spec in llm.TOOL_SPECS}
    assert names == set(tools.TOOLS)
