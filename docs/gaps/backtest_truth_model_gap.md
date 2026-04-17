# Backtest Truth Model Gap (Closed For BACKTEST-001)

## Stage

Stage 2: backtesting truth layer, accepted for the spot-first replay contract.

## Current truth

The repo now has:

- canonical SQLite truth
- explicit policy tracing
- explicit hard risk gating
- explicit execution intent
- explicit quote-backed paper settlement
- explicit spot-first backtest replay truth
- advisory realized-feedback comparison

The accepted `BACKTEST-001` slice now adds:

- `settlement/backtest.py`
- `BacktestTruthOwner`
- `backtest_session_v1`
- `backtest_fill_v1`
- `backtest_position_v1`
- `backtest_session_report_v1`

This means the repo no longer lacks a governed spot-first backtesting truth
contract.

## Closeout scope

The accepted slice now answers, explicitly and in persisted truth:

- what is a tradeable instrument
- what is a bar, bucket, or event boundary
- what is a backtest session
- what fill assumptions apply
- what fee, slippage, and latency assumptions apply
- what counts as realized PnL in paper mode
- how spot differs from future perps/futures widening

## Remaining deferred differences

What remains deferred is not the Stage 2 backtest truth contract itself, but
later widening details:

- canonical label/regime truth that will consume this replay layer
- strategy registry and challenger governance that will compare against it
- perps/futures-specific assumptions, which still belong in
  `instrument_expansion_readiness_gap.md`

## Why this file stays

This file remains in `docs/gaps/` as the closeout and routing surface for the
accepted `BACKTEST-001` slice so future loops do not reopen the same gap by
accident.
