# Paper Trading Readiness Gap

This gap tracks what still separates the current repo from a credible
Solana-first paper-trading application.

It is not a gap about basic runtime ownership. The paper runtime, execution
intent, and spot-first backtest truth are already real.

## Current truth

Already landed:

- source truth in SQLite
- bounded features
- bounded condition scoring
- explicit policy tracing
- hard risk gating
- execution intent ownership
- paper settlement and paper reports
- spot-first backtest replay truth
- advisory shadow evaluation
- bounded label-program and strategy-eval loops
- a bounded paper-runtime operator loop that reads advisory strategy output,
  creates paper intents, settles paper sessions, and writes UTC-dated QMD
  receipts

## Remaining gap

The remaining gap is trusted paper-trading selection and evidence:

- `LABEL-001` must run and be accepted on real repo data, not just fixtures
- `STRAT-001` must become a stable governed selector for advisory strategy
  families
- real-data condition history must be deep enough for the governed regime scorer
  to run without weakening thresholds
- advisory selector output still remains family-level; mint selection is explicit
  via quote provenance instead of hidden runtime inference

## Why this matters

Without this layer, the repo is still stronger as a research engine than as a
paper-trading app.

The missing value is not “more models.” The missing value is:

- trustworthy label selection
- trustworthy strategy comparison
- bounded paper-action generation
- evidence-rich operator review

## Not part of this gap

This gap does not mean the repo should widen to live trading.

Future live trading remains blocked on:

- explicit widening out of paper-only scope
- stronger readiness metrics than headline win ratio
- explicit live-risk and halt design
- explicit private-key control design

An 80% win ratio by itself is not a sufficient live-trading gate.
