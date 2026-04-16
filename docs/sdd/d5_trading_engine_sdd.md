# D5 Trading Engine SDD

## Document Status

- status: active
- scope: current software design for the source-truth stack plus bounded feature, condition, and shadow owners

## System Overview

The system is organized around an auditable, paper-first evidence pipeline:

```text
adapter client
  -> capture runner
  -> raw JSONL / raw SQL receipts
  -> source normalizer
  -> canonical SQLite truth
  -> bounded deterministic feature materialization
  -> bounded condition scoring
  -> bounded shadow evaluation
  -> optional DuckDB sync + research artifacts
```

This design keeps write authority narrow and explicit:
- SQLite is canonical truth
- DuckDB is an analytical mirror
- raw payloads remain replayable
- feature, condition, and experiment receipts remain first-class truth surfaces
- policy, risk, settlement, and promotion do not inherit authority implicitly from model outputs

## Design Principles

- Paper-first only
- Source-specific raw surfaces
- Shared canonical tables
- UTC-first event timing
- Deterministic feature inputs
- Explicit model-family receipts
- Minimal layer crossing
- Fail closed on uncertain provider or freshness behavior

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

### Source Layer

`src/d5_trading_engine/adapters/`
- provider-specific capture clients

`src/d5_trading_engine/capture/runner.py`
- owns ingest bookkeeping
- calls adapters
- writes raw files
- persists raw rows
- invokes normalizers
- records provider health

`src/d5_trading_engine/normalize/`
- owns source-specific projection into canonical truth

### Feature Layer

`src/d5_trading_engine/features/materializer.py`
- owns deterministic feature materialization from canonical truth
- enforces freshness authorization through `ingest_run` and `source_health_event`
- writes `feature_materialization_run`
- currently implements:
  - `spot_chain_macro_v1`
  - `global_regime_inputs_15m_v1`

### Condition Layer

`src/d5_trading_engine/condition/scorer.py`
- owns bounded regime scoring from feature truth
- currently implements:
  - `global_regime_v1`
- writes:
  - `condition_scoring_run`
  - `condition_global_regime_snapshot_v1`
- persists only the latest closed-bucket runtime snapshot
- exposes point-in-time-safe walk-forward regime history for shadow evaluation

### Shadow Research Layer

`src/d5_trading_engine/research_loop/shadow_runner.py`
- owns bounded experiment comparison and shadow receipts
- currently implements:
  - `intraday_meta_stack_v1`
- writes:
  - `experiment_run`
  - `experiment_metric`
  - artifact files under `data/research/shadow_runs/<run_id>/`

### Policy, Risk, Settlement, Trajectory

These package boundaries exist, and `policy/` now owns one explicit condition-to-policy evaluator plus `policy_global_regime_trace_v1`, `risk/` now owns one explicit final-veto surface through `RiskGate` plus `risk_global_regime_gate_v1`, and `settlement/` now owns one explicit quote-backed paper ledger through `PaperSettlement` plus `paper_session`, `paper_fill`, `paper_position`, and `paper_session_report`. `trajectory/` still does not own promoted forecast authority, and runtime-owned execution intent between risk and settlement remains a follow-on surface.

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

### Feature Truth

- `feature_materialization_run`
- `feature_spot_chain_macro_minute_v1`
- `feature_global_regime_input_15m_v1`

### Condition Truth

- `condition_scoring_run`
- `condition_global_regime_snapshot_v1`

### Policy Truth

- `policy_global_regime_trace_v1`

### Risk Truth

- `risk_global_regime_gate_v1`

### Settlement Truth

- `paper_session`
- `paper_fill`
- `paper_position`
- `paper_session_report`

### Shadow Truth

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
- hardened raw websocket capture with reconnect and heartbeat semantics

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
- one-minute candle capture
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

Feature-clock rules:
- `spot_chain_macro_v1` is one row per tracked mint per UTC minute bucket
- `global_regime_inputs_15m_v1` is one market-wide row per closed UTC 15-minute bucket
- macro observations are eligible only if `captured_at <= bucket_end_utc` and `observation_date <= bucket_date`

## Feature Design

### `spot_chain_macro_v1`

- grain: one row per tracked mint per UTC minute bucket
- inputs:
  - Jupiter spot price and quotes
  - Coinbase market structure
  - bounded Helius transfer activity
  - FRED macro context
- gating:
  - fails closed when required source lanes are not `healthy_recent`
- receipt:
  - `feature_materialization_run`

### `global_regime_inputs_15m_v1`

- grain: one market-wide row per UTC 15-minute bucket
- proxy preference:
  - `SOL-USD`
  - `BTC-USD`
  - `ETH-USD`
- aggregates:
  - 15-minute market return mean/std
  - 15-minute realized volatility
  - market volume and trade summaries
  - mean L2 spread
  - rolling 4-hour return and realized volatility summaries
  - macro context availability plus selected FRED values

## Condition Design

### `global_regime_v1`

- training window:
  - trailing 90 days
- minimum rows:
  - 32 closed 15-minute rows
- model family:
  - four-state Gaussian HMM when `hmmlearn` is installed
  - four-component Gaussian mixture fallback otherwise
- runtime output:
  - latest closed-bucket snapshot only
- walk-forward output:
  - point-in-time-safe history for shadow evaluation
  - refit cadence: every 4 scored 15-minute buckets
- semantic states:
  - `long_friendly`
  - `short_friendly`
  - `risk_off`
  - `no_trade`
- blocked states:
  - `risk_off`
  - `no_trade`

## Shadow Design

### `intraday_meta_stack_v1`

- regime input:
  - walk-forward regime history from `global_regime_v1`
- execution feature lane:
  - `spot_chain_macro_v1`
- labels:
  - fixed ATR-style triple-barrier labels on 5-minute bars
  - `tb_60m_atr1x`
  - `tb_240m_atr1x`
- model family:
  - `IsolationForest` anomaly flags
  - `RandomForestClassifier` baseline meta-labeler
  - `XGBClassifier` primary meta-labeler
- optional research enrichments:
  - Chronos-2 forecast when available
  - Monte Carlo summaries derived from Chronos quantiles
  - Fibonacci confluence as a research annotation only
- evidence path:
  - `data/research/shadow_runs/<run_id>/`

The shadow lane is bounded, research-only, and non-promoting. It is not policy authority.

## CLI Design

`src/d5_trading_engine/cli.py` provides the current operational surface:
- `d5 init`
- `d5 capture <provider>`
- `d5 materialize-features <feature-set>`
- `d5 score-conditions <condition-set>`
- `d5 run-shadow <shadow-run>`
- `d5 status`
- `d5 sync-duckdb [tables...]`

`d5 status` now exposes the latest condition run directly, including failed-run visibility instead of silently falling back to an older success.

## Deferred Layers

The following package surfaces remain incomplete runtime owners:

- `models/`
  - no governed model registry or promotion path
- `trajectory/`
  - no promoted scenario or forecast owner yet

## Validation Design

Default validation is offline-safe:
- config tests
- migration/bootstrap tests
- CLI tests
- mocked adapter tests
- docs contract tests
- feature/condition/shadow targeted tests

Live integration is gated separately and not part of default CI.

## Design Risks

- Helius websocket capture remains raw-first and lightly validated compared with REST.
- Coinbase currently uses public market endpoints only, so authenticated or execution-aware behavior is absent.
- Massive remains a planned source, not an operational one.
- Chronos-2 is optional in the current shadow path and may skip cleanly when its dependencies are unavailable.
- Runtime-owned execution intent, richer settlement lifecycle / mark history, and promotion-sensitive governance are still intentionally unimplemented.

## References

- [README.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/README.md)
- [docs/architecture/bootstrap_architecture.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/architecture/bootstrap_architecture.md)
- [docs/task/first_feature_input_contract.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/first_feature_input_contract.md)
- [docs/task/global_regime_condition_and_shadow_stack.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/global_regime_condition_and_shadow_stack.md)
- [docs/math/regime_shadow_modeling_contracts.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/math/regime_shadow_modeling_contracts.md)
