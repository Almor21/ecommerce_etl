install:
	uv sync --extra dev

test:
	uv run pytest -q

run:
	uv run etl

up:
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf data/bronze data/silver data/gold data/quarantine data/quality data/warehouse.duckdb warehouse.duckdb
