# First Feature Input Contract

Active execution surface for locking and extending the first real post-ingest `features/` owner by defining which canonical truth tables it may consume, what freshness assumptions should gate those inputs, and what receipt surface proves a feature run actually happened.

## Goal

Create the first bounded feature-materialization contract so downstream `condition/` work can consume deterministic feature tables instead of reading provider adapters, raw receipts, or ad hoc canonical queries directly.

## Current Truth

- `features/` now has a first bounded implementation path in `src/d5_trading_engine/features/materializer.py`
- the canonical schema now contains both the `feature_materialization_run` receipt surface and the first feature table `feature_spot_chain_macro_minute_v1`
- the repo already has real canonical source tables for:
  - spot reference and quote data
  - chain transfer and registry data
  - market candles, trades, and order book snapshots
  - macro observations
- the CLI now exposes `d5 materialize-features spot-chain-macro-v1`
- freshness authorization is now enforced from `ingest_run` and `source_health_event` receipts and persisted into `feature_materialization_run.freshness_snapshot_json`

## This Slice Covers

- naming the first feature set and its intended downstream use
- defining the canonical input tables that are allowed for the first feature set
- defining which lanes must be freshness-qualified before a feature run is considered valid
- defining the minimum receipt and audit fields for `feature_materialization_run`
- defining which source tables remain out of scope for the first feature pass

## Proposed First Feature Set

`spot_chain_macro_v1`

Intent:

- give `condition/` a single deterministic input surface for early market, chain, and macro context
- avoid any feature dependence on provider adapters, raw payloads, or placeholder research logic

## Implementation Landed

- migration `003_feature_spot_chain_macro_v1.py` creates the first bounded feature table
- `FeatureMaterializer.materialize_spot_chain_macro_v1()` writes a truthful `feature_materialization_run` row and minute-by-mint feature rows
- the first row grain is now implemented as one row per tracked mint per UTC minute bucket
- the feature lane now fails closed when any required capture lane is not `healthy_recent`
- the default CLI test suite proves the first feature run can be materialized offline from seeded canonical truth

## Allowed Canonical Inputs

| Area | Canonical tables allowed now | Why they belong |
|------|-------|-------|
| Solana spot reference | `token_price_snapshot`, `quote_snapshot`, `token_registry`, `token_metadata_snapshot` | core spot pricing, quote quality, and token identity |
| Coinbase market data | `market_instrument_registry`, `market_candle`, `market_trade_event`, `order_book_l2_event` | cross-venue market structure and liquidity context |
| Chain activity | `solana_transfer_event`, `solana_address_registry`, `program_registry` | bounded chain-state and tracked-address activity context |
| Macro context | `fred_observation`, `fred_series_registry` | low-frequency macro backdrop for later condition work |
| Runtime freshness support | `ingest_run`, `source_health_event` | not feature values themselves, but required to prove the input lanes are fresh enough |

## Explicitly Disallowed Inputs

- adapter clients under `adapters/`
- raw JSONL files under `data/raw/`
- raw source receipt tables such as `raw_jupiter_*`, `raw_helius_*`, `raw_fred_*`, and raw Coinbase payload tables
- `capture_cursor` as a substitute for real freshness qualification
- anything under placeholder runtime layers such as `condition/`, `policy/`, `risk/`, `settlement/`, `trajectory/`, or `research_loop/`

## Freshness Dependency Rule

The first feature set must only consume lanes that are currently `healthy_recent` under the continuous-capture ownership task.

Implemented now:

- `jupiter-prices` within 15 minutes
- `jupiter-quotes` within 15 minutes
- `helius-transactions` within 30 minutes
- `coinbase-products` within 24 hours
- `coinbase-candles` within 30 minutes
- `coinbase-market-trades` within 30 minutes
- `coinbase-book` within 30 minutes
- `fred-observations` within 2 days

Minimum dependency reading:

- required for spot feature materialization:
  - `jupiter-prices`
  - `jupiter-quotes`
- required for market-structure feature materialization:
  - at least one eligible Coinbase market-data lane relevant to the target product
- required for chain-aware feature materialization:
  - `helius-transactions`
  - `helius-discovery` when registry context is required
- required for macro-aware feature materialization:
  - `fred-observations`

If a required lane is `never_started`, `degraded`, or `stale`, the feature run should fail closed or explicitly downgrade scope rather than silently proceeding.

## Minimum Feature Run Receipt

The first real feature-materialization implementation should write a truthful `feature_materialization_run` row with at least:

- `run_id`
- `feature_set`
- `source_tables`
- `row_count`
- `status`
- `started_at`
- `finished_at`
- `error_message` when failed
- `created_at`

Implemented now:

- all of the required fields above
- `source_tables` populated with the canonical tables consumed by the first lane
- `status` transitions for `running`, `success`, and `failed`

Implemented now:

- `freshness_snapshot_json`
  - captures the lane-state summary used to authorize the run
- `input_window_start_utc`
  - lower time bound of the materialized feature-minute window
- `input_window_end_utc`
  - upper time bound of the materialized feature-minute window

## Output Contract Shape

The first implementation does not need a broad feature store. It only needs a small, explicit surface that proves `features/` is now a real owner.

Minimum acceptable output shape:

- one documented feature table or materialized dataset for `spot_chain_macro_v1`
- one row grain definition that is explicit about time and asset or product identity
- one mapping from source tables to derived fields
- one reproducible run receipt in `feature_materialization_run`

## Proposed First Row Grain

Use:

- one row per tracked mint
- per UTC minute bucket
- with macro context broadcast onto the same minute bucket

Why this is the strongest current fit:

- Jupiter spot and quote captures already align naturally around mint identity and UTC timing
- `solana_transfer_event` already carries mint plus UTC helper fields that can aggregate cleanly to minute buckets
- Coinbase market data can be attached through `market_instrument_registry` by matching base symbol to the tracked token identity
- FRED observations are lower-frequency and can be forward-carried or latest-known within the minute bucket without forcing a separate grain

The first row grain should therefore be described as:

- `feature_minute_utc`
- `mint`
- optional resolved market context such as the preferred Coinbase `product_id`

## Derived Field Families

The first implementation only needs a narrow, auditable field set.

Minimum field families:

- spot reference fields
  - latest Jupiter spot price
  - recent quote slippage or price-impact summary
  - quote latency summary
- market structure fields
  - latest candle close or return over the chosen bar window
  - recent trade count or size summary
  - latest book spread summary
- chain activity fields
  - transfer count in the minute bucket
  - inbound and outbound amount summaries by tracked mint
  - tracked-address activity flags where registry context exists
- macro context fields
  - latest known FRED observation values for the selected series set
- freshness fields
  - lane-state snapshot or derived eligibility flag used to authorize the feature row

Implemented now in `feature_spot_chain_macro_minute_v1`:

- spot reference fields
  - `jupiter_price_usd`
  - `quote_count`
  - `mean_quote_price_impact_pct`
  - `mean_quote_response_latency_ms`
- market structure fields
  - `coinbase_close`
  - `coinbase_trade_count`
  - `coinbase_trade_size_sum`
  - `coinbase_book_spread_bps`
- chain activity fields
  - `chain_transfer_count`
  - `chain_amount_in`
  - `chain_amount_out`
- macro context fields
  - `fred_dff`
  - `fred_t10y2y`
  - `fred_vixcls`
  - `fred_dgs10`
  - `fred_dtwexbgs`
- identity and time fields
  - `feature_minute_utc`
  - `mint`
  - `symbol`
  - `coinbase_product_id`
  - `event_date_utc`
  - `hour_utc`
  - `minute_of_day_utc`
  - `weekday_utc`

## Join Discipline

The first feature implementation should follow these join rules:

- join on canonical token identity first, not provider-local symbols alone
- treat `token_registry` and `token_metadata_snapshot` as identity support, not as direct feature outputs by themselves
- allow Coinbase market context only when product metadata resolves cleanly to a tracked asset
- aggregate chain events by UTC minute and mint before joining into the feature row
- broadcast macro observations as latest-known context, not as a separate per-observation grain

## Deferred On Purpose

- broad feature catalog design
- model-ready tensor or ML pipeline abstractions
- feature serving or online inference infrastructure
- policy or risk logic
- research-loop automation
- widening Helius into deep protocol-aware decoding

## Next Actions After This Slice

1. decide the fail-closed versus latest-known policy for sparse minute buckets instead of relying only on current latest-row behavior
2. decide whether freshness thresholds stay code-local or move into explicit operator policy/config
3. descend into `docs/task/global_regime_condition_and_shadow_stack.md` so the first condition scorer and shadow lane keep consuming feature truth instead of falling back to canonical source tables
