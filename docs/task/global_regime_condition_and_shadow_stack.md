# Global Regime Condition And Shadow Stack

## Purpose

Active execution surface for the first real `condition/` owner and the first governed `research_loop/` shadow lane.

This note documents the HMM-style regime scorer, the bounded fallback behavior when `hmmlearn` is unavailable, and the shadow-only meta-stack that keeps Chronos, Monte Carlo, anomaly detection, Random Forest, and XGBoost out of runtime authority.

## Implemented Commands

- `d5 materialize-features global-regime-inputs-15m-v1`
  - materializes a 15-minute market-wide feature table from canonical truth
- `d5 score-conditions global-regime-v1`
  - fits the first bounded regime model and writes a condition receipt
- `d5 run-shadow intraday-meta-stack-v1`
  - runs the shadow-only ensemble and writes experiment receipts plus evidence artifacts
- `d5 status`
  - now shows the latest condition run and regime snapshot alongside ingest health

## Truth Surfaces

### Feature truth

- `feature_global_regime_input_15m_v1`
  - 15-minute market-wide regime inputs
- `feature_materialization_run`
  - stores freshness snapshots plus source input windows for both feature lanes

### Condition truth

- `condition_scoring_run`
  - records source feature run, training window, model family, and semantic-state map
- `condition_global_regime_snapshot_v1`
  - stores the latest scored 15-minute bucket with raw state, semantic regime, confidence, and blocked flag

### Shadow truth

- `experiment_run`
  - tracks the bounded shadow evaluation run
- `experiment_metric`
  - stores metric rows for anomaly rate, dataset size, and model-family outcomes
- `data/research/shadow_runs/<run_id>/`
  - stores JSON artifacts and a QMD report without promoting them into runtime authority

## Input Contract

### Global regime features

`global_regime_inputs_15m_v1` consumes only canonical truth:

- Coinbase product registry
- one-minute Coinbase candles
- Coinbase market trades
- Coinbase book snapshots
- optional FRED macro context, forward-filled within a relaxed freshness window

The current proxy set prefers `BTC-USD`, `ETH-USD`, and `SOL-USD` and rolls those into one market-wide 15-minute row.

### Condition scoring

`global_regime_v1` trains on a rolling 90-day window of 15-minute regime inputs and emits one of:

- `long_friendly`
- `short_friendly`
- `risk_off`
- `no_trade`

When `hmmlearn` is available, the scorer uses a four-state Gaussian HMM. When it is not available, it falls back to a four-component Gaussian mixture proxy and records that model family explicitly in the receipt.

Macro staleness does not block scoring in v1. It degrades confidence instead, while required market-structure lanes still fail closed at the feature layer.

## Shadow Stack Scope

`intraday_meta_stack_v1` is shadow-only. It does not widen runtime authority.

Current shadow components:

- HMM-aligned regime history from `global_regime_v1`
- `spot_chain_macro_v1` as the minute-level execution feature lane
- fixed ATR-style triple-barrier labels on 5-minute bars
- `IsolationForest` anomaly flags
- `RandomForestClassifier` baseline meta-labeler
- `XGBClassifier` primary meta-labeler
- optional Chronos-2 forecast with a graceful skip path when Chronos is unavailable
- Monte Carlo summaries derived from the Chronos quantile forecast
- Fibonacci confluence as a research annotation only

The runner writes `success` even when Chronos is unavailable, as long as the bounded shadow models still produce evaluable receipts.

## Policy Stub

The first semantic-regime to advisory-bias mapping now lives at:

- `src/d5_trading_engine/policy/global_regime_v1_bias_map.yaml`

This file is intentionally advisory-only. It exists so later `policy/` work reads YAML instead of silently baking semantic-to-bias assumptions into code.

## Not Yet Safe To Claim

This slice does **not** mean the repo has:

- strategy eligibility
- a paper-session loop
- a hard risk gate
- settlement receipts
- governed model promotion

The truthful claim is narrower:

- `condition/` now has one bounded regime scorer backed by feature truth
- `research_loop/` now has one bounded shadow experiment lane with non-promoting receipts
- runtime policy, risk, and settlement remain unimplemented

## Next Actions

1. Turn the advisory YAML bias map into the first real `policy/` trace input instead of leaving it file-only.
2. Define the first `condition/` to `policy/` consumer so regime state becomes explainable eligibility rather than a standalone score.
3. Add the first paper-safe `risk/` veto surface before any strategy or settlement work expands.
4. After paper-session receipts exist, connect `experiment_run` comparison to realized paper outcomes rather than pure shadow labels.
