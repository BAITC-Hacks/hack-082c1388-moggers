"""Проверка ответа: каждый упомянутый gid должен существовать в выгрузке."""
from __future__ import annotations

import re

# gid в этом датасете — 18-значное число; берём с запасом от 15 цифр.
GID_REF = re.compile(r"\b\d{15,20}\b")
SENTENCE = re.compile(r"(?<=[.!?])\s+")


def mentioned_gids(text: str) -> set[int]:
    return {int(m) for m in GID_REF.findall(text)}


def validate(text: str, known: set[int]) -> tuple[str, list[str]]:
    """Удаляет предложения со ссылками на несуществующие gid."""
    kept, warnings = [], []
    for sentence in SENTENCE.split(text.strip()):
        if not sentence:
            continue
        unknown = mentioned_gids(sentence) - known
        if unknown:
            warnings.append(
                f"Удалено утверждение со ссылкой на отсутствующие узлы "
                f"({', '.join(str(x) for x in sorted(unknown))}): {sentence[:120]}")
            continue
        kept.append(sentence)
    return " ".join(kept), warnings


def is_grounded(text: str, known: set[int]) -> bool:
    refs = mentioned_gids(text)
    return bool(refs) and refs.issubset(known)
