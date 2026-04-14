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

## Live-Gated Helius Integration

Run this only when you intentionally want a live Helius receipt and have both `HELIUS_API_KEY` and `HELIUS_TRACKED_ADDRESSES` available through `.env` or the environment:

```bash
pytest --run-integration tests/test_integration_helius.py -q
```

What this proves:

- tracked-address discovery can write raw JSONL files plus `raw_helius_account_discovery` rows
- enhanced transaction capture can write raw JSONL files plus `raw_helius_enhanced_transaction` rows
- the bounded canonical Helius truth tables (`program_registry`, `solana_address_registry`, `solana_transfer_event`) can be populated
- `source_health_event` and `ingest_run` receipts are recorded for the REST/discovery path
- the bounded websocket path can write raw acknowledgement and notification rows when tracked addresses emit a live transaction during the test window
- the websocket receipt also depends on the configured Helius plan allowing `transactionSubscribe`
- DuckDB can sync the canonical Helius tables from SQLite

## Manual Operator Smoke Checks

After copying `.env.example` to `.env` and filling in the provider keys you plan to use:

```bash
d5 init
d5 status
d5 capture jupiter-tokens
d5 capture jupiter-prices
d5 capture jupiter-quotes
d5 capture helius-discovery
d5 capture helius-transactions
d5 capture helius-ws-events
d5 capture coinbase-products
d5 capture fred-observations
d5 materialize-features spot-chain-macro-v1
d5 sync-duckdb ingest_run source_health_event token_registry token_price_snapshot quote_snapshot program_registry solana_address_registry solana_transfer_event feature_materialization_run feature_spot_chain_macro_minute_v1

sqlite3 data/db/d5.db ".tables"
find data/raw -maxdepth 3 -type f | sort
```

These smoke checks prove:

- the storage layer can create runtime directories
- the SQLite truth surface can be migrated to the declared Alembic head
- Jupiter can write spot metadata, price, and quote receipts
- Helius discovery, transfer capture, and bounded websocket capture can write tracked-address receipts
- Coinbase can write raw product receipts without sharing the truth DB
- the first bounded `features/` lane can materialize `spot_chain_macro_v1` from canonical truth
- `d5 materialize-features spot-chain-macro-v1` fails closed when required lane health receipts are missing
- DuckDB can mirror selected canonical tables

Additional behavior checks:

- `d5 capture helius-transactions` fails clearly when `HELIUS_TRACKED_ADDRESSES` is missing
- `d5 capture massive-crypto` fails closed with a real operator-visible error on auth, entitlement, or placeholder-endpoint failures
- `d5 status` shows the separate Coinbase raw DB path

## Known Validation Limits

- live provider integration is not part of the default test pass or CI
- Coinbase market-data coverage is currently public-market capture only
- Massive capture remains a fail-closed readiness/probe surface
- Helius websocket behavior is hardened for bounded raw capture, but it still has no durable resumability policy and no canonical websocket projection
