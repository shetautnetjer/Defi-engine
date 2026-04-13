# Bootstrap Validation

Current validation surface for the ingest bootstrap plus the source-expansion pre-conditions slice.

## Offline Default Checks

```bash
cd /home/netjer/Projects/AI-Frame/Brain/Defi-engine
pip install -e ".[dev]"
python -m compileall src/d5_trading_engine
PYTHONPATH=src python -m d5_trading_engine.cli --help
pytest tests -q
ruff check src tests
```

What these checks prove:

- the current Python package imports and compiles
- the Click CLI loads and exposes the documented command surface
- Alembic bootstrap, config loading, docs truth contracts, and mocked adapter seams are covered under pytest
- default pytest stays offline-safe even with live integration tests present in the repo
- the touched pre-conditions seam is lint-clean for the repo rules

## Live-Gated Jupiter Integration

Run this only when you intentionally want a live provider receipt and have a valid `JUPITER_API_KEY` available through `.env` or the environment:

```bash
pytest --run-integration tests/test_integration_jupiter.py -q
```

What this proves:

- `d5 init` can create the canonical SQLite truth DB through Alembic
- a real Jupiter tokens + prices path can write raw JSONL files
- raw SQL rows and canonical SQLite rows are populated
- `source_health_event` and `ingest_run` receipts are recorded
- DuckDB can be created and synced from the selected SQLite truth tables

## Manual Operator Smoke Checks

After copying `.env.example` to `.env` and filling in the provider keys you plan to use:

```bash
d5 init
d5 status
d5 capture jupiter-tokens
d5 capture jupiter-prices
d5 capture jupiter-quotes
d5 capture helius-discovery
d5 capture coinbase-products
d5 sync-duckdb ingest_run source_health_event token_registry token_price_snapshot quote_snapshot

sqlite3 data/db/d5.db ".tables"
find data/raw -maxdepth 3 -type f | sort
```

These smoke checks prove:

- the storage layer can create runtime directories
- the SQLite truth surface can be migrated to the declared Alembic head
- Jupiter can write spot metadata, price, and quote receipts
- Helius discovery can write tracked-address raw receipts
- Coinbase can write raw product receipts without sharing the truth DB
- DuckDB can mirror selected canonical tables

Additional behavior checks:

- `d5 capture helius-transactions` fails clearly when `HELIUS_TRACKED_ADDRESSES` is missing
- `d5 capture massive-crypto` fails closed with a real operator-visible error on auth, entitlement, or placeholder-endpoint failures
- `d5 status` shows the separate Coinbase raw DB path

## Known Validation Limits

- live provider integration is not part of the default test pass or CI
- Coinbase market-data coverage is currently public-market capture only
- Massive capture remains a fail-closed readiness/probe surface
- Helius websocket behavior is bounded raw capture, not hardened streaming infrastructure
