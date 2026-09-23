"""Сессия ассистента: LLM с инструментами, либо детерминированный режим без ключа.

Пайплайн и выгрузки считаются локально и от ассистента не зависят — он надстройка.
Без ключа вопросы всё равно обрабатываются: разбор намерения и те же инструменты,
только формулировка шаблонная.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import llm, prompts
from .tools import TOOLS, GraphContext
from .validator import validate
from .scope import ARITHMETIC, REFUSAL, locally_relevant

GID_IN_QUESTION = re.compile(r"\b\d{15,20}\b")


@dataclass
class Answer:
    text: str
    tools_used: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    llm_used: bool = False

    def __str__(self) -> str:
        return self.text


class Assistant:
    """Держит граф в памяти между вопросами: загрузка занимает секунды, ответ — нет."""

    def __init__(self, data_dir: Path = Path("data"), out_dir: Path = Path("out")):
        self.ctx = GraphContext.from_dirs(data_dir, out_dir)
        self.history: list[dict[str, Any]] = []

    def ask(self, question: str, use_llm: bool | None = None) -> Answer:
        if ARITHMETIC.search(question):
            return Answer(REFUSAL)
        use_llm = llm.available() if use_llm is None else (use_llm and llm.available())
        if not use_llm:
            if not locally_relevant(question, bool(self.history)):
                return Answer(REFUSAL)
            return self._offline(question)
        try:
            allowed = llm.in_scope(question, self.history)
        except Exception:
            # Fail closed: an unavailable topic check must not unlock a general chatbot.
            return Answer("Не удалось проверить тему запроса. Попробуйте ещё раз. " + REFUSAL)
        if not allowed:
            return Answer(REFUSAL)
        try:
            return self._with_llm(question)
        except Exception as exc:  # демо не должно падать из-за внешнего API
            offline = self._offline(question)
            offline.warnings.append(f"LLM недоступен ({exc}), ответ собран детерминированно.")
            return offline

    # ---------------------------------------------------------------- режимы

    def _with_llm(self, question: str) -> Answer:
        used: list[str] = []

        def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
            fn = TOOLS.get(name)
            if fn is None:
                return {"error": f"нет инструмента {name}"}
            try:
                return fn(self.ctx, **args)
            except TypeError as exc:
                return {"error": f"неверные аргументы {name}: {exc}"}

        messages = [{"role": "system", "content": prompts.SYSTEM}]
        messages += self.history
        messages.append({"role": "user", "content": f"{question}\n\n{prompts.ANSWER_STYLE}"})

        raw = llm.run(messages, dispatch, on_step=lambda n, a: used.append(n))
        text, warnings = validate(raw, self.ctx.known_gids)
        if not text.strip():
            fallback = self._offline(question)
            fallback.warnings.append("Ответ модели не прошёл проверку ссылок на узлы.")
            return fallback

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-8:]
        return Answer(text=text, tools_used=used, warnings=warnings, llm_used=True)

    def _offline(self, question: str) -> Answer:
        tool, args = self._route(question)
        result = TOOLS[tool](self.ctx, **args)
        return Answer(text=_render(tool, result), tools_used=[tool],
                      warnings=["Режим без LLM: ответ собран по шаблону "
                                "(задайте OPENAI_API_KEY для связного ответа)."])

    def _route(self, q: str) -> tuple[str, dict[str, Any]]:
        """Разбор намерения по ключевым словам — запасной путь без модели."""
        low = q.lower()
        gids = [int(x) for x in GID_IN_QUESTION.findall(q)]

        if len(gids) >= 2 and any(w in low for w in ("сходят", "собирает", "общ", "пересек")):
            return "convergence", {"gids": gids}
        if len(gids) >= 2 and any(w in low for w in ("путь", "маршрут", "как деньги", "дойти", "трасс")):
            return "trace_money", {"src": gids[0], "dst": gids[1]}
        if gids and any(w in low for w in ("убрать", "изъ", "заблок", "удал", "устойчив")):
            return "removal_impact", {"gids": gids}
        if gids and any(w in low for w in ("возврат", "цикл", "обратно", "встречн")):
            return "return_flows", {"gid": gids[0]}
        if gids and any(w in low for w in ("не хватает", "запрос", "пробел", "полнот", "чего нет")):
            return "data_gaps", {"gid": gids[0]}
        if gids and any(w in low for w in ("плат", "контрагент", "получател", "отправител", "связ")):
            return "counterparties", {"gid": gids[0]}
        if gids:
            return "node_profile", {"gid": gids[0]}

        cluster = re.search(r"кластер\w*\s*#?(\d+)", low)
        if cluster:
            return "cluster_profile", {"cluster_id": int(cluster.group(1))}
        for role, words in (("coordinator", ("координ", "организат")),
                            ("consolidator", ("консолид", "собира")),
                            ("distributor", ("распредел", "веер")),
                            ("transit", ("транзит",)),
                            ("terminal", ("конечн", "сток"))):
            if any(w in low for w in words):
                return "find_nodes", {"role": role, "limit": 10}
        return "find_nodes", {"limit": 10}


# ---------------------------------------------------------------- рендер без LLM

def _money(x: float) -> str:
    return f"{x / 1e6:.2f} млн ₸" if x >= 1e6 else f"{x / 1e3:.0f} тыс ₸"


def _render(tool: str, r: dict[str, Any]) -> str:
    if "error" in r:
        return r["error"]

    if tool == "node_profile":
        return (f"Узел [{r['gid']}] — {r['role_ru']} (уверенность {r['role_score']}), "
                f"приоритет {r['priority_score']}, кластер #{r['cluster_id']}, колено {r['depth']}. "
                f"{r['evidence']} Деньги доходят от {r['seed_sources']} seed-клиентов.")

    if tool == "find_nodes":
        if not r["nodes"]:
            return "Под условие не подошёл ни один узел."
        lines = [f"  [{n['gid']}] {n['role_ru']}, приоритет {n['priority_score']}: {n['evidence']}"
                 for n in r["nodes"]]
        return f"Найдено узлов: {r['found']}. Первые по приоритету:\n" + "\n".join(lines)

    if tool == "convergence":
        if not r["nodes"]:
            return r["note"] or "Общих точек сбора не найдено."
        lines = [f"  [{n['gid']}] {n['role_ru']} — деньги доходят от "
                 f"{n['reached_from_n_sources']} из указанных счетов, приоритет {n['priority_score']}"
                 for n in r["nodes"][:10]]
        return (f"Средства указанных счетов сходятся на {r['converging_nodes']} узлах "
                f"в пределах {r['max_hops']} колен:\n" + "\n".join(lines))

    if tool == "trace_money":
        if not r.get("paths"):
            return r.get("note", "Маршрутов не найдено.")
        p = r["paths"][0]
        chain = " -> ".join([str(p["steps"][0]["from"])] + [str(s["to"]) for s in p["steps"]])
        return (f"Найдено маршрутов: {r['paths_found']}. Кратчайший ({p['length']} шага): {chain}. "
                f"Самый узкий участок — {_money(p['bottleneck_kzt'])}.")

    if tool == "counterparties":
        parts = []
        for key, label in (("payers", "Платят узлу"), ("receivers", "Получают от узла")):
            if r.get(key):
                items = ", ".join(f"[{x['gid']}] {_money(x['sum_kzt'])}" for x in r[key][:8])
                parts.append(f"{label}: {items}.")
        return f"Контрагенты узла [{r['gid']}]. " + " ".join(parts)

    if tool == "cluster_profile":
        roles = ", ".join(f"{k}: {v}" for k, v in r["roles"].items())
        top = ", ".join(f"[{n['gid']}]" for n in r["top_nodes"])
        return (f"Кластер #{r['cluster_id']}: {r['n_nodes']} узлов, {r['n_seed']} seed, "
                f"оборот {_money(r['total_flow_kzt'])}. Состав: {roles}. Ключевые узлы: {top}.")

    if tool == "removal_impact":
        removed = ", ".join(f"[{g}]" for g in r["removed"])
        return (f"Изъятие узлов {removed} отрезает {r['share_cut_off']:.0%} сети от seed-клиентов "
                f"({r['reachable_from_seeds_before']} -> {r['reachable_from_seeds_after']} узлов), "
                f"сеть распадается с {r['components_before']} до {r['components_after']} компонент, "
                f"затронут оборот {r['flow_removed_readable']}.")

    if tool == "return_flows":
        if not r["pairs"]:
            return (f"У узла [{r['gid']}] встречных переводов нет"
                    + (f", но он входит в замкнутую цепочку из {r['min_cycle_len']} узлов."
                       if r["min_cycle_len"] else "."))
        pairs = "; ".join(f"[{p['gid']}]: отправлено {_money(p['sent_kzt'])}, "
                          f"вернулось {_money(p['received_back_kzt'])}" for p in r["pairs"][:6])
        return f"У узла [{r['gid']}] деньги возвращаются от {r['reciprocal_partners']} счетов. {pairs}."

    if tool == "data_gaps":
        gaps = " ".join(r["gaps"])
        asks = " ".join(f"{i}. {a}" for i, a in enumerate(r["suggested_requests"], 1))
        return f"Про узел [{r['gid']}]: {gaps}" + (f" Что запросить: {asks}" if asks else "")

    return str(r)


def answer(question: str, data_dir: Path = Path("data"),
           out_dir: Path = Path("out"), use_llm: bool | None = None) -> Answer:
    """Разовый вопрос без сохранения сессии."""
    return Assistant(data_dir, out_dir).ask(question, use_llm)
