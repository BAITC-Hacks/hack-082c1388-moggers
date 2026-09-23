"""Человекочитаемые формулировки: склонение числительных и аккуратная обрезка.

Evidence читает аналитик, а не парсер, поэтому согласование важно.
"""
from __future__ import annotations


def plural(n: int, one: str, few: str, many: str) -> str:
    """Русские три формы: 1 кластер, 2 кластера, 5 кластеров."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def count(n: int, one: str, few: str, many: str) -> str:
    return f"{n} {plural(n, one, few, many)}"


def payers(n: int) -> str:
    """Родительный падеж после «от»: от 1 плательщика, от 5 плательщиков."""
    return f"{n} {'плательщика' if n % 10 == 1 and n % 100 != 11 else 'плательщиков'}"


def receivers_dat(n: int) -> str:
    return f"{n} {'получателю' if n % 10 == 1 and n % 100 != 11 else 'получателям'}"


def receivers_acc(n: int) -> str:
    return f"{n} {'получателя' if n % 10 == 1 and n % 100 != 11 else 'получателей'}"


def kzt(x: float) -> str:
    return f"{x / 1e6:.1f} млн ₸" if x >= 1e6 else f"{x / 1e3:.0f} тыс ₸"


def compose(parts: list[str], limit: int = 200) -> str:
    """Собирает evidence из фрагментов по убыванию важности, пока они влезают в лимит.

    Лимит в 200 символов задан ТЗ. Без приоритизации обрезка съедала бы
    самые содержательные признаки, стоящие в конце строки.
    """
    out = ""
    for part in parts:
        part = " ".join(part.split())
        if not part:
            continue
        candidate = f"{out} {part}".strip()
        if len(candidate) <= limit:
            out = candidate
    return out or fit(parts[0] if parts else "", limit)


def fit(s: str, limit: int = 200) -> str:
    """Обрезает по границе слова — evidence не должен обрываться на полуслове."""
    s = " ".join(s.split())
    if len(s) <= limit:
        return s
    cut = s[: limit - 1]
    if " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,.;:") + "…"
