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

### Policy

- `global_regime_v1`
  - explicit condition-to-policy evaluator with policy-local YAML loading
- `policy_global_regime_trace_v1`
  - first explicit traceable eligibility receipt surface (`eligible_long`, `eligible_short`, `no_trade`)

### Risk

- `risk/`
  - package boundary for final veto ownership
- `RiskGate`
  - explicit hard gate over persisted policy truth
- `risk_global_regime_gate_v1`
  - first persisted risk verdict receipt surface (`allowed`, `no_trade`, `halted`)

### Settlement

- `settlement/`
  - package boundary for paper session and settlement ownership
- `PaperSettlement`
  - deterministic quote-backed settlement service requiring explicit `risk_verdict_id` plus `quote_snapshot_id`
- `paper_session`
- `paper_fill`
- `paper_position`
- `paper_session_report`
  - first settlement-owned paper ledger and reporting truth

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

## Remaining runtime blockers

- continuous capture ownership still needs an explicit runtime cadence and freshness owner
- risk-to-settlement execution intent is still explicit-id only; there is no runtime-owned instrument or size selection surface yet
- `research_loop/` still does not compare shadow outputs against realized paper outcomes
- the orchestration layer still needs a clean terminal completion contract so backlog exhaustion, audit-known follow-ons, and terminal completion are governed states instead of implicit outcomes

## Current repo-local docs to read first

- `README.md`
- `docs/README.md`
- `docs/project/bootstrap_inventory.md`
- `docs/task/global_regime_condition_and_shadow_stack.md`
- `docs/issues/paper_runtime_blockers.md`
- `docs/math/regime_shadow_modeling_contracts.md`
- `docs/runbooks/feature_condition_shadow_cycle.md`

## Current safe framing

- current repo = source truth + bounded features + bounded condition + explicit
  policy traces + explicit risk gate + explicit paper settlement + bounded shadow
- target repo = governed paper engine with continuous capture ownership,
  explicit execution intent, realized feedback governance, and auditable promotion controls

## Orchestration rule

Unless an actual blocker is discovered, future stories should bias toward:

1. `ORCH-005` until terminal completion and finder-governed follow-on promotion are explicit
2. the remaining blockers in `docs/issues/paper_runtime_blockers.md`
3. execution-intent hardening or realized-feedback governance only when the gap is receipt-backed
4. policy or risk follow-on only when a real downstream blocker requires it

Keep the 4-lane swarm fixed. Finder work happens inside the existing research
and architecture lanes and stays advisory until writer-integrator promotes it.
