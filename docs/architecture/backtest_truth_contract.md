# Backtest Truth Contract

## Purpose

This document describes the accepted `BACKTEST-001` contract: a
settlement-owned, spot-first replay ledger that makes paper-vs-backtest
comparison explicit without widening into strategy generation or derivatives
semantics.

## Owner

`src/d5_trading_engine/settlement/backtest.py`

Public owner:

- `BacktestTruthOwner`

## Scope

`BacktestTruthOwner` owns only three operations:

- `open_spot_session(...)`
- `record_fill(...)`
- `close_session(...)`

It does not:

- choose trades
- generate strategy signals
- define labels
- widen into leverage, funding, or liquidation logic
- imply live execution authority

## Persisted Truth

The backtest replay ledger persists these canonical SQLite tables:

- `backtest_session_v1`
- `backtest_fill_v1`
- `backtest_position_v1`
- `backtest_session_report_v1`

The shape intentionally mirrors the paper ledger closely enough for direct
comparison of:

- `cash_usdc`
- `position_value_usdc`
- `equity_usdc`
- `realized_pnl_usdc`
- `unrealized_pnl_usdc`
- `mark_method`
- `mark_inputs_json`
- `reason_codes_json`

## Governing Assumptions

The accepted v1 contract is intentionally narrow:

- `instrument_family = spot`
- `venue = jupiter_spot`
- `base_currency = USDC`
- no leverage
- no funding
- no liquidation
- no margin

Each session persists explicit replay assumptions for:

- `bucket_granularity`
- `fee_bps`
- `slippage_bps`
- `latency_ms`
- `mark_method`

The owner fails closed on:

- unsupported instrument families
- invalid assumption values
- non-monotonic fill timestamps
- unsupported or untracked mints
- missing mark inputs for open positions at close

## Data Flow

The backtest truth flow is:

```text
replay setup
  -> BacktestTruthOwner.open_spot_session(...)
  -> BacktestTruthOwner.record_fill(...)
  -> BacktestTruthOwner.close_session(...)
  -> backtest_session_report_v1
```

This sits alongside, not inside, the paper runtime flow:

```text
policy trace
  -> risk verdict
  -> execution_intent_v1
  -> PaperSettlement
  -> paper_session_report
```

The contract exists so future strategy and research work can compare governed
paper and backtest outcomes without inventing ad hoc semantics.

## Non-Goals

This slice does not claim:

- canonical regime or label truth
- strategy-family governance
- perps/futures replay semantics
- promotion of research outputs into runtime authority

Those remain separate later-stage surfaces.
