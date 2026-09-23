"""Назначение ролей: формальные правила с порогами и обоснование с числами.

Правила проверяются в порядке приоритета — от самой содержательной роли
к самой слабой. Первое сработавшее и определяет роль узла.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .text import count, fit, kzt as _kzt, payers as _payers
from .text import receivers_acc as _receivers_acc, receivers_dat as _receivers_dat


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _unexplained(r) -> str:
    """Исходящие больше видимых входящих — деньги пришли вне периметра выгрузки."""
    if r.out_kzt < cfg.UNEXPLAINED_MIN_OUTFLOW_KZT:
        return ""
    if r.in_kzt <= 0:
        return " Входящих в выгрузке нет вовсе — источник средств вне периметра."
    if r.out_kzt / r.in_kzt >= cfg.UNEXPLAINED_OUTFLOW_RATIO:
        return f" Отдаёт в {r.out_kzt / r.in_kzt:.0f}× больше видимых входящих: источник вне выгрузки."
    return ""


def assign_roles(f: pd.DataFrame) -> pd.DataFrame:
    """Возвращает колонки role, role_score, evidence для каждого узла."""
    bt_cut = f.betweenness.quantile(cfg.COORDINATOR_BETWEENNESS_PCT)
    # Порог «заметной суммы» для оборванных узлов — медиана входящих среди тех,
    # у кого вообще есть входящие. Абсолютных цифр не выдумываем.
    sink_cut = f.loc[f.in_kzt > 0, "in_kzt"].median()

    roles, scores, evidence = [], [], []
    for r in f.itertuples(index=False):
        role, score, why = _classify(r, bt_cut, sink_cut)
        roles.append(role)
        scores.append(round(_clip01(score), 3))
        evidence.append(fit(why, 200))

    return pd.DataFrame({"gid": f.gid, "role": roles,
                         "role_score": scores, "evidence": evidence})


def _classify(r, bt_cut: float, sink_cut: float) -> tuple[str, float, str]:
    """Роль, уверенность и обоснование одного узла — единственный источник правды."""
    role, score, why = _rules(r, bt_cut, sink_cut)
    # Вывод, опирающийся на оборванную выгрузку, не может быть таким же уверенным.
    if r.depth_truncated and role != "terminal_unverified":
        score *= cfg.TRUNCATION_SCORE_PENALTY
        why += " Обход оборван на 4-м колене — исходящие могли не попасть в выгрузку."
    return role, score, why


def _rules(r, bt_cut: float, sink_cut: float) -> tuple[str, float, str]:
    collects = r.in_deg >= cfg.CONSOLIDATOR_MIN_IN_DEG
    spreads = r.out_deg >= cfg.DISTRIBUTOR_MIN_OUT_DEG

    # 1. Координатор: одновременно собирает и перераспределяет, либо структурно
    #    связывает несколько кластеров на путях от нескольких seed.
    # Двусторонний узел: собранное должно объяснять раздачу, иначе это вливание
    # средств извне, а не консолидация (проверка ловушки «только исходящие»).
    balanced = r.in_kzt >= cfg.COORDINATOR_MIN_FLOW_BALANCE * r.out_kzt
    if collects and spreads and balanced:
        score = 0.6 + 0.2 * min(r.seed_sources / 5, 1) + 0.2 * min(r.out_deg / 60, 1)
        return "coordinator", score, (
            f"Собирает от {_payers(r.in_deg)} ({_kzt(r.in_kzt)}) и раздаёт "
            f"{_receivers_dat(r.out_deg)} ({_kzt(r.out_kzt)}); деньги доходят от "
            f"{r.seed_sources} seed. Признаки узла, управляющего потоком.")
    if (r.betweenness >= bt_cut and r.seed_sources >= cfg.COORDINATOR_MIN_SEED_SOURCES
            and r.clusters_bridged >= cfg.COORDINATOR_MIN_CLUSTERS_BRIDGED):
        score = 0.5 + 0.3 * min(r.seed_sources / 5, 1) + 0.2 * min(r.clusters_bridged / 3, 1)
        return "coordinator", score, (
            f"Посредничество в верхнем 1% (betweenness {r.betweenness:.4f}), связывает "
            f"{count(r.clusters_bridged, 'кластер', 'кластера', 'кластеров')}, "
            f"деньги доходят от {r.seed_sources} seed. "
            f"Вход {r.in_deg}, выход {r.out_deg}. Признаки координации." + _unexplained(r))

    # 2. Точка консолидации: сбор доминирует над раздачей.
    if collects and r.in_deg >= cfg.CONSOLIDATOR_ASYMMETRY * max(r.out_deg, 1):
        score = 0.55 + 0.25 * min(r.in_deg / 12, 1) + 0.2 * min(r.pct_in_kzt, 1)
        extra = (f", в один день платили {r.max_payers_one_day} разных отправителей"
                 if r.max_payers_one_day >= 3 else "")
        return "consolidator", score, (
            f"Получает {_kzt(r.in_kzt)} от {_payers(r.in_deg)}, "
            f"отдаёт {_receivers_dat(r.out_deg)}{extra}. Признаки консолидации.")

    # 3. Распределитель: веер получателей.
    if spreads and r.out_deg >= cfg.DISTRIBUTOR_ASYMMETRY * max(r.in_deg, 1):
        score = 0.55 + 0.25 * min(r.out_deg / 60, 1) + 0.2 * min(r.pct_out_kzt, 1)
        return "distributor", score, (
            f"Раздаёт {_kzt(r.out_kzt)} на {_receivers_acc(r.out_deg)} при "
            f"{_payers(r.in_deg)}; средний перевод {_kzt(r.avg_out_tx_kzt)}. "
            f"Признаки веерного распределения." + _unexplained(r))

    # 4. Транзит: пропускает дальше, не удерживая. Для seed не считаем —
    #    входящие суммы у них занижены устройством выгрузки.
    if (r.in_deg > 0 and r.out_deg > 0 and not r.is_seed
            and not np.isnan(r.pass_through)
            and cfg.TRANSIT_PASS_LOW <= r.pass_through <= cfg.TRANSIT_PASS_HIGH):
        # Одна операция у порога 5 000 ₸ — это не транзитная инфраструктура,
        # поэтому уверенность масштабируется оборотом.
        volume = min(r.flow_kzt / cfg.TRANSIT_FULL_CONFIDENCE_KZT, 1.0)
        base = 0.45 + 0.3 * (1 - abs(1 - r.pass_through)) + 0.25 * r.fast_pass_share
        score = base * (0.45 + 0.55 * volume)
        speed = (f", {r.fast_pass_share:.0%} ушло в первые "
                 f"{cfg.TRANSIT_FAST_DAYS} дня" if r.fast_pass_share > 0 else "")
        return "transit", score, (
            f"Пропустил {r.pass_through:.0%} полученного дальше: принял "
            f"{_kzt(r.in_kzt)} от {_payers(r.in_deg)}, отдал {_kzt(r.out_kzt)} "
            f"на {_receivers_acc(r.out_deg)}{speed}. Признаки транзита.")

    # 5. Конечный получатель — только там, где обход не оборван.
    if (r.depth <= cfg.TERMINAL_MAX_DEPTH and r.in_kzt > 0
            and (r.out_deg == 0 or (not np.isnan(r.pass_through)
                                    and r.pass_through <= cfg.TERMINAL_MAX_PASS))):
        retained = r.in_kzt - r.out_kzt
        score = 0.5 + 0.3 * min(r.pct_in_kzt, 1) + 0.2 * min(r.in_deg / 5, 1)
        return "terminal", score, (
            f"Принял {_kzt(r.in_kzt)} от {_payers(r.in_deg)} и удержал "
            f"{_kzt(retained)}; обход на колене {r.depth} не обрывался, "
            f"значит отсутствие исходящих — поведение, а не артефакт.")

    # 6. Оборванный сток: похоже на конечного получателя, но проверить нельзя.
    if r.depth_truncated and (r.in_deg >= 2 or r.in_kzt >= sink_cut):
        score = 0.35 + 0.15 * min(r.in_deg / 5, 1)
        return "terminal_unverified", score, (
            f"Принял {_kzt(r.in_kzt)} от {_payers(r.in_deg)}, исходящих нет — "
            f"но узел на 4-м колене, где обход остановлен. Отличить конечного "
            f"получателя от необследованного нельзя без выгрузки на 5-е колено.")

    # 7. Периферия.
    if r.in_deg == 0 and r.out_deg == 0:
        return "peripheral", 0.9, (
            f"Нет ни одного перевода в выгрузке (seed={bool(r.is_seed)}): все операции "
            f"узла либо ниже порога 5 000 ₸, либо вне периметра выгрузки.")
    return "peripheral", 0.6, (
        f"Вход: {_payers(r.in_deg)} ({_kzt(r.in_kzt)}), выход: "
        f"{_receivers_acc(r.out_deg)} ({_kzt(r.out_kzt)}) — ни один порог роли "
        f"не пройден." + _unexplained(r))
