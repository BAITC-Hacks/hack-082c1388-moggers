"""Ранжирование: кого аналитику смотреть первым и почему."""
from __future__ import annotations

import pandas as pd

from . import config as cfg
from .text import count


def _norm(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    return (s - lo) / (hi - lo) if hi > lo else s * 0.0


def compute(f: pd.DataFrame) -> pd.DataFrame:
    """priority_score — взвешенная сумма нормированных компонент (веса в config)."""
    w = cfg.PRIORITY_WEIGHTS
    parts = pd.DataFrame({
        "role": f.role.map(cfg.ROLE_PRIORITY).fillna(cfg.ROLE_PRIORITY["peripheral"]),
        "seed_sources": _norm(f.seed_sources),
        "betweenness": _norm(f.betweenness),
        "flow": _norm(f.flow_kzt),
        "structure": f.structure_score,
        "pagerank": _norm(f.pagerank),
        "fan": _norm(f.in_deg + f.out_deg),
    })
    score = sum(parts[k] * w[k] for k in w)
    # Уверенность в роли масштабирует приоритет: слабое основание — ниже в списке.
    score = score * (0.6 + 0.4 * f.role_score)

    out = f[["gid"]].copy()
    out["priority_score"] = score.round(4).clip(0, 1)
    out["why"] = [_why(r, parts.loc[i]) for i, r in enumerate(f.itertuples(index=False))]
    return out


def _why(r, part: pd.Series) -> str:
    """Называет два главных вклада в приоритет — чтобы ранг был проверяем."""
    top = part.drop(labels=["role"]).sort_values(ascending=False).head(2)
    names = {
        "seed_sources": f"деньги доходят от {count(r.seed_sources, 'seed-клиента', 'seed-клиентов', 'seed-клиентов')}",
        "betweenness": f"стоит на путях сети (betweenness {r.betweenness:.4f})",
        "flow": f"оборот {(r.in_kzt + r.out_kzt) / 1e6:.1f} млн ₸",
        "structure": _structure_reason(r),
        "pagerank": f"влияние с учётом сумм (pagerank {r.pagerank:.4f})",
        "fan": f"связей: {r.in_deg} входящих, {r.out_deg} исходящих",
    }
    drivers = "; ".join(names[k] for k in top.index)
    return f"{cfg.ROLE_RU.get(r.role, r.role)}. {drivers}."[:300]


def _structure_reason(r) -> str:
    bits = []
    if r.reciprocal_partners:
        bits.append(f"деньги возвращаются отправителю "
                    f"({count(r.reciprocal_partners, 'встречный счёт', 'встречных счёта', 'встречных счетов')})")
    elif r.min_cycle_len:
        bits.append(f"входит в замкнутую цепочку из {r.min_cycle_len} узлов")
    if r.is_articulation:
        bits.append("точка сочленения: изъятие разрывает связность")
    return "; ".join(bits) or "структурных особенностей нет"


def top_nodes(f: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    top = (f.sort_values(["priority_score", "gid"], ascending=[False, True])
           .head(n).reset_index(drop=True))
    top.insert(0, "rank", range(1, len(top) + 1))
    return top[["rank", "gid", "role", "priority_score", "why"]]
