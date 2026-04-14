# First Feature Input Contract

Active execution surface for turning `features/` into the first real post-ingest runtime owner by defining which canonical truth tables it may consume, what freshness assumptions gate those inputs, and what receipt surface proves a feature run actually happened.

## Goal

Create the first bounded feature-materialization contract so downstream `condition/` work can consume deterministic feature tables instead of reading provider adapters, raw receipts, or ad hoc canonical queries directly.

## Current Truth

- `features/` is currently an empty placeholder package
- the canonical schema already contains a receipt scaffold in `feature_materialization_run`
- the repo already has real canonical source tables for:
  - spot reference and quote data
  - chain transfer and registry data
  - market candles, trades, and order book snapshots
  - macro observations
- no current repo doc says which of those tables are legal inputs to the first feature set, how they should be freshness-qualified, or what output shape should count as a real feature run

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

If a required lane is `never_started`, `degraded`, `stale`, or `readiness_only`, the feature run should fail closed or explicitly downgrade scope rather than silently proceeding.

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

Recommended extension fields for the first migration after implementation starts:

- `freshness_snapshot_json`
  - captures the lane-state summary used to authorize the run
- `input_window_start_utc`
  - lower time bound of the materialized input window
- `input_window_end_utc`
  - upper time bound of the materialized input window

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

1. lock the minute-by-mint row grain for `spot_chain_macro_v1` unless code review finds a stronger current fit
2. define the first concrete derived fields inside each field family
3. add the first implementation path in `features/` plus a truthful `feature_materialization_run` write path
