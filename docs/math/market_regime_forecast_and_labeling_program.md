# Market Regime, Forecast, and Labeling Program

This file defines the mathematical truth surfaces that research and runtime
work must align to before deeper model promotion is considered.

## Canonical direction labels

The first canonical directional labels are:

- `up`
- `down`
- `flat`
- `invalid`
- `low_confidence`

The implementation should define these from explicit horizon and threshold
rules, not from informal chart reading.

Required label properties:

- horizon is explicit
- threshold is explicit
- fees/slippage sensitivity can be replayed
- uncertain windows do not get forced into false certainty

## Regime taxonomy

Regimes should be described as explicit, composable classes rather than
hand-wavy narratives.

Minimum regime families:

- trend regime
- volatility regime
- liquidity regime
- macro or cross-market stress regime

Every regime surface needs:

- inputs
- cadence
- confidence
- invalid / unknown handling
- failure-closed behavior when inputs are stale or malformed

## Forecast horizons

Forecasts and labels must state their horizon explicitly. Suggested program
levels:

- short intraday horizon
- session horizon
- multi-session comparison horizon

Direction accuracy without horizon discipline is not useful.

## Evaluation metrics

Research and promotion should compare:

- hit rate by regime
- precision / recall for `up`, `down`, and `flat`
- calibration quality
- average return by signal bucket
- max drawdown
- risk-adjusted outcome metrics
- turnover sensitivity
- fee/slippage sensitivity
- out-of-sample robustness
- regime-transition robustness

Directional correctness alone is insufficient.

## Role of research tools

### Chronos-2

Use first as a research-only forecast comparator and context generator.

### Monte Carlo

Use for path sensitivity, confidence ranges, drawdown distribution, and
robustness checks.

### Fibonacci

Treat as an optional feature family or annotation set. It must compete with
baselines and remain removable.

### autoresearch

Use to generate bounded hypotheses, experiment candidates, and literature
comparisons. It may not bless runtime authority directly.

### ANN / relationship modeling

Use as a research-only way to explore cross-asset, cross-regime, or
cross-signal structure until a deterministic promotion path exists.

## Promotion rule

Forecasting and labeling experiments may produce evidence. They do not become
runtime truth until:

- inputs are explicit and deterministic
- metrics are defined and replayable
- failure modes are documented
- risk compatibility is explicit
- writer-integrator accepts a promotion-backed slice
