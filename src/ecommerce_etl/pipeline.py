from __future__ import annotations

import logging

from . import bronze, config, gold, serve, silver

log = logging.getLogger("ecommerce_etl")

# Silver order matters: each table's referential-integrity check reads its parent's
# cleaned Silver, so parents are built first.
SILVER_STEPS = [
    ("customers", silver.run_customers),
    ("products", silver.run_products),
    ("orders", silver.run_orders),
    ("order_items", silver.run_order_items),
    ("payments", silver.run_payments),
    ("reviews", silver.run_reviews),
]


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    log.info("== BRONZE ==")
    for name in config.TABLES:
        bronze.run(name)
    log.info("  ingested %d tables", len(config.TABLES))

    log.info("== SILVER ==")
    for name, run in SILVER_STEPS:
        df = run()
        log.info("  %-12s %6d rows", name, df.height)

    log.info("== GOLD ==")
    for name, df in gold.run().items():
        log.info("  %-25s %6d rows", name, df.height)

    log.info("== SERVE (DuckDB) ==")
    serve.run()
    log.info("  warehouse -> %s", config.WAREHOUSE_DB)

    log.info("== pipeline complete ==")


if __name__ == "__main__":
    main()
