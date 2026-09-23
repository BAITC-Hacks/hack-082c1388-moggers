#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v node >/dev/null || ! node -e 'const [major,minor]=process.versions.node.split(".").map(Number); process.exit(major>22 || (major===22 && minor>=12) ? 0 : 1)'; then
  echo "Для frontend нужен Node.js >=22.12. Используйте Node.js 22 (frontend/.nvmrc)." >&2
  exit 1
fi
if [ ! -x .venv/bin/python ]; then
  "${PYTHON:-python3}" -m venv .venv
fi
if ! .venv/bin/python -c 'import moneygraph, fastapi, uvicorn, pandas, pyarrow, scipy, networkx' 2>/dev/null; then
  .venv/bin/python -m pip install -e '.[web]'
fi
if [ ! -f frontend/node_modules/.moneygraph-package-lock ] || ! cmp -s frontend/package-lock.json frontend/node_modules/.moneygraph-package-lock; then
  npm ci --prefix frontend --no-audit --no-fund
  cp frontend/package-lock.json frontend/node_modules/.moneygraph-package-lock
fi
PYTHONPATH=src .venv/bin/python -m moneygraph.pipeline --data data --out out
npm run build --prefix frontend
echo "MoneyGraph: http://127.0.0.1:8000"
PYTHONPATH=src exec .venv/bin/python -m uvicorn moneygraph.api:app --host 127.0.0.1 --port 8000
