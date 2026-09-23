.PHONY: run test clean

# Полный пересчёт от сырых parquet до трёх выгрузок.
run:
	./run.sh

test:
	PYTHONPATH=src python3 -m pytest -q

clean:
	rm -rf out
