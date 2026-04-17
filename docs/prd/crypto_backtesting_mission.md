# Crypto Backtesting Mission

`Defi-engine` is a paper-first, Solana-first crypto backtesting and paper-trading
platform that learns and compares regime-aware strategies under strict
evidence, risk, and promotion governance.

## Mission

Build an auditable engine that can:

- classify `up`, `down`, and `flat` market windows
- detect and compare market regimes
- decide strategy eligibility under explicit policy and risk contracts
- run paper settlement and paper reporting without implying live trading
- compare research ideas against realized paper outcomes before promotion

The north star is not “more models.” The north star is better governed paper
outcomes with explicit contracts, reproducible evidence, and bounded drawdown.

## Current truthful scope

Implemented now:

- canonical source truth in SQLite
- bounded feature materialization
- bounded regime scoring
- explicit policy tracing
- explicit risk gating
- explicit quote-backed paper settlement
- bounded shadow evaluation

Still missing as governed runtime owners:

- continuous capture ownership across required lanes
- runtime-owned execution intent between `risk/` and `settlement/`
- realized-feedback comparison between `research_loop/` and paper outcomes

## Product target

The governed product descent is:

1. truthful paper runtime and backtesting truth
2. explicit regime and label truth
3. strategy comparison and promotion governance
4. instrument widening only after the lower truth surfaces are stable

Future widening order:

1. Solana spot
2. Jupiter spot strategy depth
3. Jupiter perps
4. Coinbase futures

Perps and futures are intentional future-stage targets. They are not current
runtime authority.

## Research-only surfaces until promoted

These stay advisory until they earn promotion through explicit contracts,
validation, and receipt-backed acceptance:

- Chronos-2
- Monte Carlo analysis
- Fibonacci-derived feature families
- autoresearch / automated hypothesis generation
- ANN / relationship modeling
- feature search and broad experiment generation

Research systems may propose, compare, and critique. They may not silently
become runtime authority.

## Success criteria

The product is improving when it produces:

- profitable paper outcomes after fees and slippage assumptions
- bounded drawdown and explicit no-trade behavior
- regime-aware strategy comparison
- calibration that improves direction and eligibility confidence
- auditable receipts for why a strategy, regime, or paper action was accepted

It is not succeeding merely because it has more indicators, more models, or
more files.
