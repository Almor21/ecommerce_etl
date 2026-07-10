install:
	uv sync --extra dev

test:
	uv run pytest -q

requirements:
	uv export --no-dev --no-emit-project --no-annotate -o requirements.txt

run:
	uv run etl

up:
	docker compose up --build

down:
	docker compose down

clean:
	rm -rf data/bronze data/silver data/gold data/quarantine data/quality data/warehouse.duckdb warehouse.duckdb
