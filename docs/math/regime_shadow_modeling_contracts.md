# Regime And Shadow Modeling Contracts

## Purpose

This document is the bounded mathematical and modeling contract for the current `Defi-engine` feature, condition, and shadow surfaces.

It exists to make the implemented math auditable without overclaiming model authority.

## Scope And Non-Claims

This document describes only what is currently implemented or explicitly reserved in the current slice.

It does **not** imply:

- governed model promotion
- live trading

The current truthful claim is narrower:

- deterministic feature construction exists
- one bounded regime scorer exists
- one bounded shadow-only ensemble exists
- explicit policy, risk, settlement, and advisory realized-feedback comparison
  now exist as downstream owners
- all model outputs remain non-promoting until they are explicitly promoted

## Data And Time Discipline

All implemented math is downstream of canonical truth.

Allowed authorities:

- canonical SQLite source tables
- `feature_materialization_run`
- `condition_scoring_run`
- `condition_global_regime_snapshot_v1`
- `experiment_run`
- `experiment_metric`

Disallowed as mathematical authority:

- raw JSONL payloads
- provider adapters
- Hindsight memory
- research artifacts by themselves

Clock rules:

- source events prefer `source_event_time_utc` when present
- otherwise they fall back to `captured_at_utc`
- feature rows use explicit UTC bucket grains
- FRED values are only eligible for a bucket when:
  - `observation_date <= bucket_date`
  - `captured_at <= bucket_end_utc`

That second rule is critical: same-day macro prints must not leak into earlier buckets before they were actually captured.

## Feature Math

### `spot_chain_macro_v1`

Grain:

- one row per tracked mint
- per UTC minute bucket

Input families:

- Jupiter spot reference
- Jupiter quote-quality summaries
- Coinbase market-structure summaries
- bounded Helius transfer summaries
- captured-at-safe FRED macro context

Current field families:

- spot reference
  - `jupiter_price_usd`
  - `quote_count`
  - `mean_quote_price_impact_pct`
  - `mean_quote_response_latency_ms`
- market structure
  - `coinbase_close`
  - `coinbase_trade_count`
  - `coinbase_trade_size_sum`
  - `coinbase_book_spread_bps`
- chain activity
  - `chain_transfer_count`
  - `chain_amount_in`
  - `chain_amount_out`
- macro context
  - `fred_dff`
  - `fred_t10y2y`
  - `fred_vixcls`
  - `fred_dgs10`
  - `fred_dtwexbgs`

Gating:

- the feature run fails closed if required lanes are not `healthy_recent`
- freshness receipts are persisted into `feature_materialization_run.freshness_snapshot_json`

### `global_regime_inputs_15m_v1`

Grain:

- one market-wide row
- per closed UTC 15-minute bucket

Proxy preference:

- `SOL-USD`
- `BTC-USD`
- `ETH-USD`

Current aggregate definitions:

- `market_return_mean_15m`
  - arithmetic mean of available per-product 15-minute returns in the bucket
- `market_return_std_15m`
  - standard deviation of available per-product 15-minute returns in the bucket
- `market_realized_vol_15m`
  - arithmetic mean of available per-product intra-bucket realized vol estimates
- `market_volume_sum_15m`
  - sum of proxy-product 15-minute volumes
- `market_trade_count_15m`
  - sum of proxy-product trade counts
- `market_trade_size_sum_15m`
  - sum of proxy-product traded size
- `market_book_spread_bps_mean_15m`
  - arithmetic mean of proxy-product spread summaries
- `market_return_mean_4h`
  - compounded return over the rolling 4-hour return buffer
- `market_realized_vol_4h`
  - standard deviation over the rolling 4-hour return buffer

Macro context:

- selected FRED values are forward-carried only after they were actually captured for the relevant bucket
- `macro_context_available` is a binary indicator that at least one configured macro value was available for the bucket

## Condition Math

### `global_regime_v1`

Purpose:

- score one bounded global market regime from `global_regime_inputs_15m_v1`

Training contract:

- training window: trailing 90 days
- minimum rows: 32 closed 15-minute rows
- state count: 4

Model family contract:

- preferred model:
  - four-state Gaussian HMM when `hmmlearn` is installed
- bounded fallback:
  - four-component Gaussian mixture proxy when `hmmlearn` is unavailable

### External `doc_ref`

Current external dependency references for the bounded regime owner:

- [`hmmlearn` tutorial](https://hmmlearn.readthedocs.io/en/latest/tutorial.html)
  - current lightweight HMM surface that matches the repo's present
    implementation shape
- [`hmmlearn` README](https://github.com/hmmlearn/hmmlearn/blob/main/README.rst)
  - primary-source maintenance note; the project explicitly says it is under
    limited-maintenance mode
- [`statsmodels` Markov switching dynamic regression models](https://www.statsmodels.org/dev/examples/notebooks/generated/markov_regression.html)
  - strongest next evaluation candidate for a small bounded trading engine if
    the repo later compares alternatives in shadow
- [`pomegranate` Hidden Markov Models tutorial](https://pomegranate.readthedocs.io/en/latest/tutorials/B_Model_Tutorial_4_Hidden_Markov_Models.html)
  - broader research-only HMM alternative, not the first next runtime
    candidate

Current posture:

- keep `hmmlearn` plus the current GMM fallback as runtime-adjacent truth
- treat `statsmodels` as the first shadow-only comparison candidate before any
  dependency swap
- keep `pomegranate` research-only unless the narrower `statsmodels` comparison
  proves insufficient
- execute that bounded comparison through
  `d5 run-shadow regime-model-compare-v1`, which stays advisory-only and does
  not change the regime owner by itself

Semantic-state contract:

- raw latent state ids are not the operator-facing truth
- runtime uses semantic regime labels derived after fit
- current semantic label surface:
  - `long_friendly`
  - `short_friendly`
  - `risk_off`
  - `no_trade`

Blocked semantics:

- `risk_off`
- `no_trade`

Confidence:

- confidence is the maximum predicted state probability for the scored row
- macro staleness degrades confidence rather than pretending the macro context is current

Persistence contract:

- runtime scoring persists only the latest closed-bucket snapshot
- shadow evaluation uses walk-forward history and must not rely on a one-shot full-window fit

## Walk-Forward Regime History

The shadow lane uses a point-in-time-safe regime history.

Current walk-forward rules:

- scoring cadence: every closed 15-minute bucket
- refit cadence: every 4 scored buckets
- each refit uses only the trailing 90-day window available at that point in time
- intermediate buckets reuse the most recent fitted model for inference only

Required walk-forward metadata:

- `bucket_start_utc`
- `raw_state_id`
- `semantic_regime`
- `confidence`
- `model_family`
- `model_epoch_bucket_start_utc`
- `training_window_start_utc`
- `training_window_end_utc`

This is the minimum contract that keeps the shadow evidence point-in-time auditable.

## Shadow Modeling Contract

### `intraday_meta_stack_v1`

Purpose:

- evaluate whether bounded regime and execution-context setups look predictive under research-only conditions

Inputs:

- walk-forward regime history from `global_regime_v1`
- minute-by-mint execution features from `spot_chain_macro_v1`
- 5-minute market bars derived from Coinbase one-minute candles

### Label Construction

Current label families:

- `tb_60m_atr1x`
  - 12 bars of 5-minute horizon
- `tb_240m_atr1x`
  - 48 bars of 5-minute horizon

Barrier rule:

- upper barrier = current close + ATR(14)
- lower barrier = current close - ATR(14)
- label = `1` if the upper barrier is hit before the lower barrier within the horizon
- label = `0` otherwise

This is a symmetric ATR-style triple-barrier setup. It is meant to test setup quality first, not encode a final reward policy.

### Meta-Models

Current bounded stack:

- `IsolationForest`
  - anomaly filter / anomaly-rate evidence
- `RandomForestClassifier`
  - interpretable baseline meta-labeler
- `XGBClassifier`
  - primary bounded meta-labeler

Evaluation contract:

- the dataset is sorted chronologically before the train/test split
- the current split is a bounded train-ratio contract, not a production promotion rule
- model outcomes are persisted only as experiment receipts and artifact evidence

### Chronos, Monte Carlo, And Fibonacci

Current contract:

- Chronos-2 is optional
- if Chronos dependencies are unavailable, the shadow run may still succeed
- Monte Carlo summaries are derived from Chronos quantile output when Chronos is available
- Fibonacci is a research annotation only

That means the current repo does **not** yet treat Chronos, Monte Carlo, or Fibonacci confluence as runtime authority.

## Research-Only Extensions

These are valid future research directions, but they are not current runtime truth:

- richer Monte Carlo or “Marco-style” scenario stacks beyond the current bounded summaries
- ANN-based relationship or manifold models across market, chain, and macro features
- multi-regime ensembles beyond the current four-state bounded scorer
- policy-conditioned reward geometry
- paper-session outcome comparison and promotion-sensitive calibration

If any of those become implemented, they should land in this directory as separate contracts rather than being implied from notebooks, memory, or discussion.

## Current Safe Summary

The current mathematical posture of the repo is:

- deterministic feature math from canonical truth
- one bounded four-state regime scorer
- one bounded, point-in-time-safe shadow ensemble
- explicit receipts for feature, condition, and experiment runs
- no policy, risk, settlement, or promotion authority derived from these models yet
