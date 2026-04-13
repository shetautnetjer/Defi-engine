# D5 Trading Engine SDD

## Document Status

- status: active
- scope: current software design for the bootstrap plus source-preconditions surface

## System Overview

The system is organized around an auditable ingest pipeline:

```text
adapter client
  -> capture runner
  -> raw JSONL / raw SQL receipts
  -> source normalizer
  -> canonical SQLite truth
  -> optional DuckDB sync
```

This design keeps write authority narrow and explicit:
- SQLite is canonical truth
- DuckDB is an analytical mirror
- raw payloads remain replayable

## Design Principles

- Paper-first only
- Source-specific raw surfaces
- Shared canonical tables
- UTC-first event timing
- Minimal layer crossing
- Fail closed on uncertain provider behavior

## Runtime Surfaces

### Config

`src/d5_trading_engine/config/settings.py` owns:
- provider keys and URLs
- tracked mint universe
- quote sizing defaults
- Helius tracked-address parsing
- Coinbase secrets-file parsing
- canonical and provider-specific DB paths

### Common Helpers

`src/d5_trading_engine/common/` owns:
- logging
- UTC helpers
- common exceptions

### Storage

`src/d5_trading_engine/storage/truth/`
- canonical SQLAlchemy engine and models
- Alembic is migration authority

`src/d5_trading_engine/storage/analytics/`
- DuckDB mirroring only

`src/d5_trading_engine/storage/raw_store.py`
- provider/date JSONL writes

`src/d5_trading_engine/storage/coinbase_raw/`
- separate raw SQLite store for Coinbase payloads

## Canonical Data Model

### Infrastructure

- `ingest_run`
- `capture_cursor`
- `source_health_event`

### Raw Truth Receipts

- `raw_jupiter_token_response`
- `raw_jupiter_price_response`
- `raw_jupiter_quote_response`
- `raw_helius_enhanced_transaction`
- `raw_helius_ws_event`
- `raw_helius_account_discovery`
- `raw_fred_series_response`
- `raw_fred_observation_response`
- `raw_massive_crypto_event`

### Canonical Source Tables

- `token_registry`
- `token_metadata_snapshot`
- `token_price_snapshot`
- `quote_snapshot`
- `fred_series_registry`
- `fred_observation`
- `program_registry`
- `solana_address_registry`
- `solana_transfer_event`
- `market_instrument_registry`
- `market_candle`
- `market_trade_event`
- `order_book_l2_event`

### Research Scaffolding

- `feature_materialization_run`
- `experiment_run`
- `experiment_metric`

## Provider Design

### Jupiter

Owned files:
- `adapters/jupiter/client.py`
- `normalize/jupiter/normalizer.py`

Current behavior:
- spot-only
- token metadata capture
- price capture
- two-sided quote capture
- throttled by `JUPITER_MIN_REQUEST_INTERVAL_SECONDS`

Canonical outputs:
- `token_registry`
- `token_metadata_snapshot`
- `token_price_snapshot`
- `quote_snapshot`

### Helius

Owned files:
- `adapters/helius/client.py`
- `adapters/helius/ws_client.py`
- `normalize/helius/normalizer.py`

Current behavior:
- tracked-address discovery via RPC
- enhanced transaction capture
- bounded transfer projection
- raw websocket capture scaffold

Canonical outputs:
- `program_registry`
- `solana_address_registry`
- `solana_transfer_event`

### Coinbase

Owned files:
- `adapters/coinbase/client.py`
- `normalize/coinbase/normalizer.py`
- `storage/coinbase_raw/`

Current behavior:
- public product discovery
- candle capture
- recent trade capture
- L2 snapshot capture
- raw payloads land in separate Coinbase SQLite DB

Canonical outputs:
- `market_instrument_registry`
- `market_candle`
- `market_trade_event`
- `order_book_l2_event`

### FRED

Owned files:
- `adapters/fred/client.py`
- `normalize/fred/normalizer.py`

Current behavior:
- series metadata capture
- observation capture

Canonical outputs:
- `fred_series_registry`
- `fred_observation`

### Massive

Owned files:
- `adapters/massive/client.py`
- `normalize/massive/normalizer.py`

Current behavior:
- fail-closed readiness path only

## Time Design

Event-style canonical tables use:
- `captured_at_utc`
- `source_event_time_utc`
- `source_time_raw`
- `event_date_utc`
- `hour_utc`
- `minute_of_day_utc`
- `weekday_utc`
- `time_quality`

Primary clock rule:
- use `source_event_time_utc` when present
- fall back to `captured_at_utc` when provider event time is absent

## CLI Design

`src/d5_trading_engine/cli.py` provides a generic operational surface:
- `d5 init`
- `d5 capture <provider>`
- `d5 status`
- `d5 sync-duckdb [tables...]`

This keeps the surface small while provider behavior is still settling.

## Deferred Layers

The following package surfaces exist as placeholders and ownership boundaries, not active runtime behavior:

- `condition/`
- `features/`
- `policy/`
- `risk/`
- `settlement/`
- `models/`
- `research_loop/`
- `trajectory/`

## Validation Design

Default validation is offline-safe:
- config tests
- migration/bootstrap tests
- CLI tests
- mocked adapter tests
- docs contract tests

Live integration is gated separately and not part of default CI.

## Design Risks

- Helius websocket capture remains raw-first and lightly validated compared with REST.
- Coinbase currently uses public market endpoints only, so authenticated or execution-aware behavior is still absent.
- Massive remains a planned source, not an operational one.
- The downstream trading runtime layers are still intentionally unimplemented.

## References

- [README.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/README.md)
- [docs/architecture/bootstrap_architecture.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/architecture/bootstrap_architecture.md)
- [docs/task/source_expansion_preconditions.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/source_expansion_preconditions.md)
- [docs/plans/source_expansion_preconditions.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/plans/source_expansion_preconditions.md)
