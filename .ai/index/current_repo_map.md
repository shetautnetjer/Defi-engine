# Current Repo Map

This is the fast orientation surface for the Defi-engine swarm.

Read this before proposing new files, modules, or runtime claims.

## Current implemented runtime-adjacent surfaces

### Source truth

- canonical SQLite truth
- raw JSONL receipt capture
- DuckDB sync on demand
- provider seams for Jupiter, Helius, Coinbase, FRED

### Features

- `spot_chain_macro_v1`
  - minute-by-mint execution-context feature lane
- `global_regime_inputs_15m_v1`
  - market-wide 15-minute regime input lane
- `feature_materialization_run`
  - truthful receipts with freshness snapshots and input windows

### Condition

- `global_regime_v1`
  - bounded regime scorer
- `condition_scoring_run`
- `condition_global_regime_snapshot_v1`

### Shadow / research loop

- `intraday_meta_stack_v1`
  - bounded shadow-only lane
- triple-barrier labels
- `IsolationForest`
- `RandomForest`
- `XGBoost`
- optional Chronos-2 summaries
- Monte Carlo summaries from quantiles
- Fibonacci as research annotation only

## Still-missing runtime owners

- `policy/`
- `risk/`
- `settlement/`

These remain the active missing owners. Do not claim a governed paper engine
until they are real.

## Current repo-local docs to read first

- `README.md`
- `docs/README.md`
- `docs/project/bootstrap_inventory.md`
- `docs/task/global_regime_condition_and_shadow_stack.md`
- `docs/issues/paper_runtime_blockers.md`
- `docs/math/regime_shadow_modeling_contracts.md`
- `docs/runbooks/feature_condition_shadow_cycle.md`

## Current safe framing

- current repo = source truth + bounded features + bounded condition + bounded
  shadow
- target repo = governed paper engine with policy, risk, settlement, and
  auditable feedback

## Orchestration rule

Unless an actual blocker is discovered, future stories should bias toward:

1. `policy/`
2. `risk/`
3. `settlement/`
