# Bootstrap Architecture

Current architecture for the implemented `Defi-engine` paper-first stack.

## Core Flow

```text
Adapter client
  -> CaptureRunner
  -> Raw JSONL landing zone
  -> raw SQL receipts
  -> source normalizer
  -> canonical SQLite truth tables
  -> bounded feature materialization
  -> bounded condition scoring
  -> bounded shadow evaluation
  -> optional DuckDB sync + research artifacts
```

This remains a paper-only engine. No live order routing, wallet automation, policy-owned eligibility, hard risk gating, or paper settlement loop is implemented here.

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

### Research artifact surface

- shadow artifacts land under `data/research/shadow_runs/<run_id>/`
- these files are evidence, not runtime authority

### Reserved storage surface

- `data/parquet/` directories are created by the storage layer
- Parquet export is not implemented yet, so this path should be treated as reserved rather than active

## Capture Ownership

- `adapters/`
  - provider-specific fetchers
  - Jupiter is the current spot reference source
  - Helius includes tracked-address REST discovery and bounded raw websocket capture
  - Coinbase provides public spot market-data capture
  - Massive remains a fail-closed readiness/probe path only

- `capture/runner.py`
  - owns ingest bookkeeping
  - calls adapters
  - writes raw files
  - persists raw rows
  - invokes normalizers
  - records provider health

- `normalize/`
  - owns source-specific projection into canonical truth
  - Jupiter projects spot tokens, prices, and quotes
  - Helius projects tracked-address discovery and bounded transfer rows
  - Coinbase projects market instruments, candles, trades, and L2 book snapshots

## Canonical Tables In Use

The active schema includes:

- infrastructure tables such as `ingest_run`, `capture_cursor`, and `source_health_event`
- raw source tables such as `raw_jupiter_*`, `raw_helius_*`, `raw_fred_*`, and `raw_massive_crypto_event`
- canonical spot and macro tables such as `token_registry`, `token_metadata_snapshot`, `token_price_snapshot`, `quote_snapshot`, `fred_series_registry`, and `fred_observation`
- chain and market event tables such as `program_registry`, `solana_address_registry`, `solana_transfer_event`, `market_instrument_registry`, `market_candle`, `market_trade_event`, and `order_book_l2_event`
- bounded feature tables such as `feature_materialization_run`, `feature_spot_chain_macro_minute_v1`, and `feature_global_regime_input_15m_v1`
- bounded condition tables such as `condition_scoring_run` and `condition_global_regime_snapshot_v1`
- bounded experiment tables such as `experiment_run` and `experiment_metric`

## Layered Runtime Owners

### `features/`

- real but bounded
- owns:
  - `spot_chain_macro_v1`
  - `global_regime_inputs_15m_v1`
- gating source freshness through `ingest_run` and `source_health_event`

### `condition/`

- real but bounded
- owns:
  - `global_regime_v1`
- runtime persistence is limited to the latest closed-bucket snapshot
- walk-forward history exists for research use only

### `research_loop/`

- real but bounded
- owns:
  - `intraday_meta_stack_v1`
- writes experiment receipts and evidence artifacts
- remains shadow-only and non-promoting

## Time Model

- event-style canonical tables store `captured_at_utc`
- when the provider emits an event time, they also store `source_event_time_utc`
- helper fields `event_date_utc`, `hour_utc`, `minute_of_day_utc`, and `weekday_utc` are materialized now so later session logic does not rely on local wall-clock time
- FRED observations are broadcast into feature rows only when the observation had already been captured by the feature bucket end

## Deliberate Non-Claims

- `features/` is not yet a broad feature store or online serving layer.
- `condition/` is not yet a broad condition catalog.
- `policy/`
- `risk/`
- `settlement/`
- `models/`
- `trajectory/`

Those package boundaries still must not be documented as active trading runtime behavior until their own owners are implemented.
