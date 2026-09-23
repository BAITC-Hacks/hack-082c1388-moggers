.PHONY: run test clean web api

# Полный пересчёт от сырых parquet до трёх выгрузок.
run:
	./run.sh

# Тесты запускаются в том же .venv, который создаёт run.sh.
test:
	@test -x .venv/bin/python || ./run.sh >/dev/null
	.venv/bin/python -m pip install -q pytest
	PYTHONPATH=src .venv/bin/python -m pytest -q

clean:
	rm -rf out

# React + API: подготовка, сборка и локальный сервер.
web:
	bash web.sh

# API для разработки (после подготовки окружения через make web).
api:
	PYTHONPATH=src .venv/bin/python -m uvicorn moneygraph.api:app --host 127.0.0.1 --port 8000
