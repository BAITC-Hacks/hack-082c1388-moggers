#!/usr/bin/env bash
# Одна команда: ставит зависимости и считает все три выгрузки в out/.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
PYTHONPATH=src python3 -m moneygraph.pipeline --data data --out out
