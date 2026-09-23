#!/usr/bin/env bash
# Одна команда: зависимости и полный пересчёт всех выгрузок в out/.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

# Ставим в локальный .venv, а не в системный Python: на многих дистрибутивах он
# защищён (PEP 668) и pip install туда просто запрещён.
if [ ! -x .venv/bin/python ]; then
  echo "Создаю виртуальное окружение .venv ..."
  "$PY" -m venv .venv 2>/dev/null || {
    echo "Не удалось создать venv. Установите пакет python3-venv и повторите." >&2
    exit 1
  }
fi

.venv/bin/python -m pip install -q --upgrade pip >/dev/null 2>&1 || true
.venv/bin/python -m pip install -q -r requirements.txt

PYTHONPATH=src .venv/bin/python -m moneygraph.pipeline --data data --out out
