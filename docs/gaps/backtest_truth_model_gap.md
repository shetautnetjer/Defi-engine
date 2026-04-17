# Backtest Truth Model Gap

## Stage

Stage 2: backtesting truth layer.

## Current truth

The repo now has:

- canonical SQLite truth
- explicit policy tracing
- explicit hard risk gating
- explicit quote-backed paper settlement
- advisory realized-feedback comparison

This means the repo is no longer missing paper ownership entirely.

## Gap

The repo still lacks one governed backtesting truth model that answers:

- what is a tradeable instrument
- what is a bar, bucket, or event boundary
- what is a backtest session
- what fill assumptions apply
- what fee, slippage, and latency assumptions apply
- what counts as realized PnL in paper mode
- how spot, perps, and futures differ

## Why it matters

Without this layer, later strategy and model work can look mathematically
interesting while still comparing against decorative or inconsistent runtime
truth.

## Close when

- a bounded backtesting contract exists in docs and code
- spot assumptions are explicit and reproducible
- perps and futures differences are documented without being prematurely
  promoted into runtime
- backtest metrics and paper metrics are comparable by design rather than by
  ad hoc interpretation
