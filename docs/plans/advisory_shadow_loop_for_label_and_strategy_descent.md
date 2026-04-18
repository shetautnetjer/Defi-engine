# Advisory Shadow Loop For Label And Strategy Descent

## Purpose

Define the bounded no-HITL research loop that should help close `LABEL-001`
and `STRAT-001` without allowing research outputs to silently become runtime
authority.

This plan is about repeated offline evaluation, not live trading and not
runtime self-promotion.

## Safe meaning of "no HITL"

For this repo, `no HITL` means:

- the research loop may repeatedly:
  - replay backtests
  - run walk-forward scoring
  - compare challengers
  - write proposal artifacts
- the loop may do that without a human choosing every trial by hand
- the loop may **not**:
  - modify runtime authority directly
  - widen scope into live execution
  - bless label or strategy promotion by itself

Writer-integrator still owns runtime and non-research promotion. The loop may
now activate the next bounded research-stage story automatically when the
machine law, metrics registry, and proposal-review receipt agree.

## Current usable foundations

The repo already has the bounded ingredients needed for an advisory research
loop:

- settlement-owned spot-first backtest truth in `settlement/backtest.py`
- point-in-time-safe walk-forward regime history
- bounded label families such as `tb_60m_atr1x` and `tb_240m_atr1x`
- anomaly and meta-model baselines in the current shadow lane:
  - `IsolationForest`
  - `RandomForestClassifier`
  - `XGBClassifier`
- explicit docs and gap surfaces for:
  - canonical labels and regime taxonomy
  - strategy registry and challenger governance
  - watcher and autoresearch adaptation

What is still missing is the contract that lets those pieces run repeatedly and
emit writer-routable evidence.

## Target loop

The advisory loop should be able to:

1. read a bounded packet for the current label or strategy study
2. open a backtest replay configuration with explicit fee/slippage/latency
   assumptions
3. generate walk-forward training and evaluation windows
4. run baseline and challenger models repeatedly
5. score the results using governed metrics
6. write proposal artifacts that say what improved, what regressed, and what is
   still advisory-only

## Bounded model families

The first repeated-loop families should stay intentionally small:

- anomaly / veto evidence:
  - `IsolationForest`
- interpretable tabular baseline:
  - `RandomForestClassifier`
- stronger bounded tabular challenger:
  - `XGBClassifier`

Chronos-2, Monte Carlo, Fibonacci, and autoresearch-style literature scouting
remain optional research helpers around this loop rather than the first models
to operationalize.

## Required outputs

Every repeated advisory run should emit durable evidence such as:

- replay assumptions
- walk-forward window definitions
- model family used
- label family used
- metric table by regime and horizon
- calibration / drawdown / expectancy comparison
- a bounded conclusion:
  - keep advisory
  - propose a label-program follow-on
  - propose a strategy-registry follow-on
  - propose subtraction because the challenger adds no value

Those outputs should route into `docs/issues/`, `docs/gaps/`, `docs/plans/`,
`docs/task/`, and then `prd.json` only through writer-integrator.

## Build order

1. watcher packet and proposal schema
   - read-only packet for repo truth and recent receipts
   - proposal artifact format for label and strategy suggestions
2. metrics registry
   - define what counts as better beyond directional accuracy
3. `LABEL-001`
   - canonical direction / horizon / confidence taxonomy
4. `STRAT-001`
   - named strategy families plus challenger and promotion artifacts
5. repeated advisory runner
   - orchestrates replay, walk-forward splits, and scoring over and over
6. writer routing
   - turns accepted findings into durable issue/gap/task/story truth

## What this closes

This plan is complete when the repo can truthfully say:

- repeated backtest and walk-forward scoring is available without human
  micromanagement
- the loop can compare bounded label and strategy challengers repeatedly
- `IsolationForest`, `RandomForestClassifier`, and `XGBClassifier` are wired as
  governed advisory model families
- writer-integrator can consume the resulting proposal artifacts and promote
  only the best next bounded slices

It does **not** close when the repo merely has more experiments or more model
outputs.
