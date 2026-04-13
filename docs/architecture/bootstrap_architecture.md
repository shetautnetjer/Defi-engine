# Bootstrap Architecture

Current architecture for the implemented `Defi-engine` bootstrap.

## Core Flow

```text
Adapter client
  -> CaptureRunner
  -> Raw JSONL landing zone
  -> raw SQL receipts
  -> source normalizer
  -> canonical SQLite truth tables
  -> optional DuckDB sync
```

This is a paper-only ingestion and research bootstrap. No live order routing, wallet automation, or promotion-sensitive runtime behavior is implemented here.

## Storage Surfaces

### Raw landing zone

- JSONL files under `data/raw/{provider}/{YYYY-MM-DD}/`
- writer: `src/d5_trading_engine/storage/raw_store.py`
- each line is wrapped in a metadata envelope containing:
  - provider
  - capture type
  - ingest run id
  - captured timestamp
  - original payload

### Canonical truth

- SQLite at `data/db/d5.db`
- engine: `src/d5_trading_engine/storage/truth/engine.py`
- schema: ORM models in `src/d5_trading_engine/storage/truth/models.py`
- migration authority: Alembic files in `sql/migrations/`, applied by `d5 init`

### Separate provider raw store

- Coinbase raw payloads also land in `data/db/coinbase_raw.db`
- this DB is a provider-specific receipt store, not a canonical authority
- normalized Coinbase rows still land in the main truth DB

### Analytics mirror

- DuckDB at `data/db/d5_analytics.duckdb`
- mirror helper: `src/d5_trading_engine/storage/analytics/duckdb_mirror.py`
- selected SQLite tables are copied into DuckDB on demand with `d5 sync-duckdb`

### Reserved storage surface

- `data/parquet/` directories are created by the storage layer
- Parquet export is not implemented yet, so this path should be treated as reserved rather than active

## Capture Ownership

- `adapters/`
  - provider-specific fetchers
  - Jupiter is the current spot reference source
  - Helius now includes tracked-address REST discovery and enhanced transactions
  - Coinbase now provides public spot market-data capture
  - Massive remains a fail-closed readiness/probe path only

- `capture/runner.py`
  - owns ingest bookkeeping
  - calls adapters
  - writes raw files
  - persists raw rows
  - invokes normalizers
  - records provider health

- `normalize/`
  - owns source-specific projection into canonical tables
  - Jupiter projects spot tokens, prices, and quotes
  - Helius projects tracked-address discovery and bounded transfer rows
  - Coinbase projects market instruments, candles, trades, and L2 book snapshots

## Canonical Tables In Use

The active schema includes:

- infrastructure tables such as `ingest_run`, `capture_cursor`, and `source_health_event`
- raw source tables such as `raw_jupiter_*`, `raw_helius_*`, `raw_fred_*`, and `raw_massive_crypto_event`
- canonical spot and macro tables such as `token_registry`, `token_metadata_snapshot`, `token_price_snapshot`, `quote_snapshot`, `fred_series_registry`, and `fred_observation`
- chain and market event tables such as `program_registry`, `solana_address_registry`, `solana_transfer_event`, `market_instrument_registry`, `market_candle`, `market_trade_event`, and `order_book_l2_event`
- research scaffolding tables such as `feature_materialization_run`, `experiment_run`, and `experiment_metric`

## Time Model

- event-style canonical tables store `captured_at_utc`
- when the provider emits an event time, they also store `source_event_time_utc`
- helper fields `event_date_utc`, `hour_utc`, `minute_of_day_utc`, and `weekday_utc` are materialized now so later session logic does not rely on local wall-clock time

## Deliberate Non-Claims

The following surfaces exist only as placeholders and are not part of the active capture path:

- `condition/`
- `features/`
- `policy/`
- `risk/`
- `settlement/`
- `models/`
- `research_loop/`
- `trajectory/`

Those packages define the intended ownership boundaries, but they should not be documented as active runtime behavior until implementation lands.
