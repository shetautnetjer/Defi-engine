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
  - shows the latest condition run alongside ingest health, including failed-run visibility instead of silently falling back to an older success receipt

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
- optional FRED macro context, forward-filled within a relaxed freshness window and only after the observation was actually captured for the relevant bucket

The current proxy set prefers `BTC-USD`, `ETH-USD`, and `SOL-USD` and rolls those into one market-wide 15-minute row.

### Condition scoring

`global_regime_v1` trains on a rolling 90-day window of 15-minute regime inputs and emits one of:

- `long_friendly`
- `short_friendly`
- `risk_off`
- `no_trade`

When `hmmlearn` is available, the scorer uses a four-state Gaussian HMM. When it is not available, it falls back to a four-component Gaussian mixture proxy and records that model family explicitly in the receipt.

The runtime scoring path persists only the latest closed-bucket snapshot. The shadow lane must use a walk-forward regime history with past-only fits and explicit refit metadata; a one-shot full-window fit is not acceptable evidence for shadow metrics.

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

Shadow metrics are provisional until the point-in-time corrective slice in `docs/issues/regime_shadow_corrective_slice.md` is closed and revalidated.

## Policy Owner

The first semantic-regime YAML policy input still lives at:

- `src/d5_trading_engine/policy/global_regime_v1_bias_map.yaml`

That YAML is now consumed by:

- `src/d5_trading_engine/policy/global_regime_v1.py`
- `policy_global_regime_trace_v1`

The accepted `POL-001` slice turns the existing YAML bias map into the first explicit `condition/ -> policy/` handoff. It emits `eligible_long`, `eligible_short`, or `no_trade` while staying fully upstream of `risk/` and `settlement/`.

## Risk Owner

The accepted `RISK-001` slice turns the existing risk scaffold into the first explicit `policy/ -> risk/` handoff. It now:

- consumes `policy_global_regime_trace_v1`
- reuses `feature_materialization_run.freshness_snapshot_json` through `source_feature_run_id`
- persists `risk_global_regime_gate_v1`
- emits explicit `allowed`, `no_trade`, or `halted` verdicts
- keeps runtime anomaly explicitly `not_owned` instead of promoting shadow signals
- stays fully upstream of `settlement/`

## Settlement Owner

The accepted `SETTLE-001` slice turns the existing settlement scaffold into the first explicit `risk/ -> settlement/` handoff. It now:

- consumes explicit `risk_verdict_id` plus `quote_snapshot_id`
- persists `paper_session`, `paper_fill`, `paper_position`, and `paper_session_report`
- keeps settlement quote-backed, paper-only, and spot-only in v1
- fails closed on stale, missing, or unsupported quote / policy / risk inputs
- leaves short-open behavior explicitly unsupported instead of inventing borrow or perp semantics

## Not Yet Safe To Claim

This slice does **not** mean the repo has:

- automatic execution intent routing from `allowed` risk verdicts into mint or size selection
- governed realized-feedback comparison inside `research_loop/`
- governed model promotion
- spot-short settlement semantics

The truthful claim is narrower:

- `condition/` now has one bounded regime scorer backed by feature truth
- `policy/` now has one explicit consumer that turns persisted condition truth into traceable `eligible_long`, `eligible_short`, or `no_trade` receipts
- `risk/` now has one explicit hard gate that turns persisted policy truth into traceable `allowed`, `no_trade`, or `halted` receipts while keeping anomaly out of runtime authority
- `settlement/` now has one explicit quote-backed paper ledger that turns persisted risk truth plus explicit quote intent into traceable paper sessions, fills, positions, and reports
- `research_loop/` now has one bounded shadow experiment lane with non-promoting receipts
- shadow remains research-only, and realized-feedback governance still remains unimplemented

## Next Actions

1. Define the first runtime-owned execution-intent surface between `risk/` and `settlement/` if the repo wants automatic paper action.
2. Keep operator wording and docs aligned so `allowed` risk verdicts do not imply automatic paper action without explicit quote-backed intent.
3. Connect `experiment_run` comparison to realized paper outcomes now that settlement receipts exist.
