"""CLI ассистента: разовый вопрос или диалог."""
from __future__ import annotations

import argparse
from pathlib import Path

from .agent import Assistant
from .agent import llm


def _print(answer) -> None:
    print("\n" + answer.text)
    if answer.tools_used:
        print(f"\n  инструменты: {', '.join(dict.fromkeys(answer.tools_used))}")
    for w in answer.warnings:
        print(f"  ! {w}")


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="moneygraph-ask",
        description="AI-ассистент аналитика: вопрос по графу на естественном языке")
    ap.add_argument("question", nargs="*", help="вопрос; без него — диалоговый режим")
    ap.add_argument("--data", default=Path("data"), type=Path)
    ap.add_argument("--out", default=Path("out"), type=Path)
    ap.add_argument("--no-llm", action="store_true", help="только детерминированный режим")
    a = ap.parse_args()

    assistant = Assistant(a.data, a.out)
    use_llm = False if a.no_llm else None
    mode = "LLM" if (use_llm is not False and llm.available()) else "детерминированный"
    print(f"Ассистент готов: {assistant.ctx.g.number_of_nodes()} узлов, режим {mode}.")

    if a.question:
        _print(assistant.ask(" ".join(a.question), use_llm))
        return 0

    print("Задайте вопрос (пустая строка — выход).")
    while True:
        try:
            q = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not q:
            return 0
        _print(assistant.ask(q, use_llm))


if __name__ == "__main__":
    raise SystemExit(main())
