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
  - deterministic quote-backed settlement service consuming explicit `execution_intent_id`
- `execution_intent/`
  - bounded paper-only owner between `risk/` and `settlement/`
- `ExecutionIntentOwner`
  - persists `execution_intent_v1` from allowed risk truth plus quote provenance
- `execution_intent_v1`
  - explicit mint, side, size, and entry-intent receipt surface
- `paper_session`
- `paper_fill`
- `paper_position`
- `paper_session_report`
  - first settlement-owned paper ledger and reporting truth
- `BacktestTruthOwner`
  - settlement-owned spot-first replay ledger with explicit session, fill,
    position, and report assumptions
- `backtest_session_v1`
- `backtest_fill_v1`
- `backtest_position_v1`
- `backtest_session_report_v1`
  - first settlement-owned backtest truth surfaces for replayable spot sessions

### Shadow / research loop

- `intraday_meta_stack_v1`
  - bounded shadow-only lane
- `label_program_v1`
  - bounded canonical direction-label scoring lane
- `strategy_eval_v1`
  - bounded named strategy-family challenger lane
- `experiment_realized_feedback_v1`
  - advisory comparison receipts between replayed shadow context and settlement-owned paper outcomes
- triple-barrier labels
- `IsolationForest`
- `RandomForest`
- `XGBoost`
- optional Chronos-2 summaries
- Monte Carlo summaries from quantiles
- Fibonacci as research annotation only
- bounded research proposal-review receipts for `LABEL-*` / `STRAT-*`
- `improvement_proposal_v1`
- `proposal_review_v1`
- `d5 review-proposal <proposal_id>`
- bounded proposal comparison and priority-selection receipts
- `proposal_comparison_v1`
- `proposal_comparison_item_v1`
- `proposal_supersession_v1`
- `d5 compare-proposals`
- bounded regime-model comparison receipts
- `regime_model_compare_v1`
- `regime_model_compare_follow_on`
- `d5 run-shadow regime-model-compare-v1`

## Remaining runtime blockers

- no remaining Stage 1 runtime-owner seam is open
- next governed blockers are label truth and strategy registry work

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
- `docs/architecture/backtest_truth_contract.md`
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
  execution intent + explicit paper settlement + bounded shadow + advisory
  realized-feedback comparison
- target repo = governed paper engine with canonical label truth,
  strategy-family governance, realized feedback governance, auditable promotion
  controls, and a staged
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
- `.ai/swarm/story_classes.yaml`
- `.ai/swarm/metrics_registry.yaml`
- `.ai/swarm/strategy_registry.yaml`
- `.ai/swarm/instrument_scope.yaml`

Writer-owned north-star curation now also depends on:

- `docs/policy/writer_story_promotion_rubric.md`
- `scripts/agents/write_story_promotion_receipt.sh`
- `.ai/dropbox/state/story_promotion_receipt.json`
- `.ai/dropbox/state/research_proposal_review_receipt.json`
- `.ai/dropbox/state/research_proposal_priority_receipt.json`

They are packet and governance truth, not live supervisor inputs in v1.
