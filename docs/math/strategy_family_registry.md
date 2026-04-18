# Strategy Family Registry

This file defines the first bounded strategy-family registry for the advisory
research loop behind `STRAT-001`.

It is a research and comparison surface only. Nothing here becomes runtime
authority without the separate promotion ladder.

## Purpose

The repo should compare named, bounded strategy families instead of treating
the shadow lane as one giant all-purpose model.

Each family must declare:

- valid instrument scope
- valid venue
- label family
- target label
- allowed regimes
- feature sets
- whether anomaly veto is required

## Current bounded families

### `trend_continuation_long_v1`

- instrument scope: `solana_spot`
- venue: `jupiter_spot`
- label family: `direction_60m_v1`
- target label: `up`
- allowed regimes:
  - `long_friendly`
- feature sets:
  - `spot-chain-macro-v1`
  - `global-regime-inputs-15m-v1`
- anomaly veto required: yes

### `trend_continuation_short_v1`

- instrument scope: `solana_spot`
- venue: `jupiter_spot`
- label family: `direction_60m_v1`
- target label: `down`
- allowed regimes:
  - `short_friendly`
- feature sets:
  - `spot-chain-macro-v1`
  - `global-regime-inputs-15m-v1`
- anomaly veto required: yes

### `flat_regime_stand_aside_v1`

- instrument scope: `solana_spot`
- venue: `jupiter_spot`
- label family: `direction_60m_v1`
- target label: `flat`
- allowed regimes:
  - `risk_off`
  - `no_trade`
- feature sets:
  - `spot-chain-macro-v1`
  - `global-regime-inputs-15m-v1`
- anomaly veto required: no

## Model families

The first repeated challenger loop should stay intentionally small:

- `IsolationForest`
  - anomaly and veto evidence only
- `RandomForestClassifier`
  - interpretable bounded baseline
- `XGBClassifier`
  - stronger bounded challenger

Chronos-2, Monte Carlo, Fibonacci, autoresearch, and ANN-style ideas remain
advisory helpers around this loop.

## Boundaries

- This registry is advisory only.
- It may create bounded challenger reports.
- It may trigger bounded research proposal review into the next
  `strategy_eval` story.
- It may not widen into runtime strategy eligibility, policy, risk, execution
  intent, or settlement authority by itself.
