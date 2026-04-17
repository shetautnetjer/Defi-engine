# Current Repo Map

This is the fast orientation surface for the Defi-engine swarm.

Read this before proposing new files, modules, or runtime claims.

## Current implemented runtime-adjacent surfaces

### Source truth

- canonical SQLite truth
- raw JSONL receipt capture
- DuckDB sync on demand
- provider seams for Jupiter, Helius, Coinbase, FRED
- `capture/lane_status.py`
  - shared capture-lane freshness owner and blocker resolver
- `d5 status`
  - operator-visible per-lane capture freshness and eligibility surface

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
- `experiment_realized_feedback_v1`
  - advisory comparison receipts between replayed shadow context and settlement-owned paper outcomes
- triple-barrier labels
- `IsolationForest`
- `RandomForest`
- `XGBoost`
- optional Chronos-2 summaries
- Monte Carlo summaries from quantiles
- Fibonacci as research annotation only

## Remaining runtime blockers

- risk-to-settlement execution intent is still explicit-id only; there is no runtime-owned instrument or size selection surface yet

## Current repo-local docs to read first

- `README.md`
- `docs/README.md`
- `docs/project/current_runtime_truth.md`
- `docs/prd/crypto_backtesting_mission.md`
- `docs/prd/backtesting_completion_definition.md`
- `docs/project/bootstrap_inventory.md`
- `docs/issues/governed_product_descent_capability_ladder.md`
- `docs/task/continuous_capture_ownership.md`
- `docs/task/global_regime_condition_and_shadow_stack.md`
- `docs/issues/paper_runtime_blockers.md`
- `docs/gaps/bootstrap_gap_register.md`
- `docs/plans/strategy_descent_and_instrument_scope.md`
- `docs/math/regime_shadow_modeling_contracts.md`
- `docs/math/market_regime_forecast_and_labeling_program.md`
- `docs/policy/runtime_authority_and_promotion_ladder.md`
- `docs/runbooks/feature_condition_shadow_cycle.md`

## Current safe framing

- current repo = source truth + explicit capture freshness owner + bounded features
  + bounded condition + explicit policy traces + explicit risk gate + explicit
  paper settlement + bounded shadow + advisory realized-feedback comparison
- target repo = governed paper engine with explicit execution intent,
  realized feedback governance, auditable promotion controls, and a staged
  Solana-first backtesting platform that widens into perps and futures only
  after the lower truth layers are strong

## Orchestration rule

Unless an actual blocker is discovered, future stories should bias toward:

1. the remaining blockers in `docs/issues/paper_runtime_blockers.md`
2. the staged backtesting story families in `prd.json` once current blocker stories are complete
3. execution-intent hardening only when the gap is receipt-backed
4. perps or futures work only when the scope ladder says widening is eligible

Keep the 4-lane swarm fixed. Finder work happens inside the existing research
and architecture lanes and stays advisory until writer-integrator promotes it.

## Machine-readable swarm law

The repo now also carries policy-only swarm governance files under `.ai/swarm/`:

- `.ai/swarm/swarm.yaml`
- `.ai/swarm/lane_rules.yaml`
- `.ai/swarm/promotion_ladder.yaml`
- `.ai/swarm/doc_owners.yaml`

Writer-owned north-star curation now also depends on:

- `docs/policy/writer_story_promotion_rubric.md`
- `scripts/agents/write_story_promotion_receipt.sh`
- `.ai/dropbox/state/story_promotion_receipt.json`

They are packet and governance truth, not live supervisor inputs in v1.
