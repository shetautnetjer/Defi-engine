# Docs Index

This directory is the repo-local routing map for documentation in `Defi-engine`.

Code, config, schema, and checks remain the runtime authority. These docs explain the current repo state, the active execution slice, and the deferred gaps without claiming unimplemented behavior.

The active repo discipline is Stage 1 current-truth consolidation: accepted
work should keep the whole `docs/` tree aligned with code truth, `prd.json`,
and `progress.txt`.

Writer-integrator is the repo's continuous truth curator. Accepted work should
flow through repo-wide docs reconciliation, issue/gap routing, and bounded story
promotion before the next slice is treated as backlog truth.

## Current Documents

- `project/bootstrap_inventory.md`
  - stable snapshot of what is implemented, partially implemented, and missing
- `project/current_runtime_truth.md`
  - compact current runtime-truth packet for the swarm
- `prd/crypto_backtesting_mission.md`
  - north-star product mission for the Solana-first paper backtesting and paper-trading platform
- `prd/backtesting_completion_definition.md`
  - explicit definition of stage completion versus terminal swarm completion
- `prd/d5_trading_engine_prd.md`
  - repo-local product requirements for the paper-first source, feature, condition, and shadow surface
- `policy/runtime_authority_and_promotion_ladder.md`
  - authority order and promotion contract for moving advisory research into governed runtime owners
- `policy/writer_story_promotion_rubric.md`
  - writer-owned routing, promotion, and north-star prioritization rules
- `sdd/d5_trading_engine_sdd.md`
  - current software design for the source-truth stack plus bounded feature, condition, policy, and shadow owners
- `architecture/backtest_truth_contract.md`
  - settlement-owned spot-first backtest session, fill, position, and report contract
- `task/ingest_hardening_phase_1.md`
  - completed hardening slice that made the bootstrap ingest contracts truthful
- `task/source_expansion_preconditions.md`
  - active bounded execution surface for mint-locked universe expansion without bypassing downstream contracts
- `task/continuous_capture_ownership.md`
  - accepted source-owner contract for freshness classes, per-lane status output, and deferred completeness follow-ons
- `task/first_feature_input_contract.md`
  - first post-ingest contract that defines which canonical truth the feature layer may consume
- `task/global_regime_condition_and_shadow_stack.md`
  - first real condition scorer plus the bounded shadow-only meta-stack and experiment receipts
- `task/reporting_and_proposals_v1.md`
  - centralized QMD reporting, SQL artifact truth, and proposal-only research review flow
- `plans/source_expansion_preconditions.md`
  - near-term sequencing for Jupiter → Helius → Coinbase source expansion
- `plans/historical_research_protocol.md`
  - future Massive-driven research and walk-forward protocol
- `plans/build_sequence_and_runtime_ownership.md`
  - bridge note from source-ingest bootstrap into downstream runtime layer ownership
- `plans/advisory_shadow_loop_for_label_and_strategy_descent.md`
  - bounded no-HITL advisory loop for repeated backtest, walk-forward, and challenger scoring in support of `LABEL-001` and `STRAT-001`
- `plans/paper_trading_readiness_and_live_gate.md`
  - bounded path from today’s research/runtime truth to a credible Solana spot paper-trading app, plus the future live-trading gate
- `plans/source_map_and_source_completeness.md`
  - provider-role map and source-completeness doctrine before downstream runtime dependence
- `plans/strategy_descent_and_instrument_scope.md`
  - governed scope ladder from Solana spot into later Jupiter perps and Coinbase futures expansion
- `gaps/bootstrap_gap_register.md`
  - deferred or missing capabilities that should not be treated as shipped
- `issues/governed_product_descent_capability_ladder.md`
  - durable issue guide for the governed product-descent target and staged capability ladder
- `gaps/backtest_truth_model_gap.md`
  - closeout surface for the accepted spot-first backtest truth slice; later widening differences remain deferred
- `gaps/label_program_and_regime_taxonomy_gap.md`
  - canonical label and regime taxonomy work still missing
- `gaps/strategy_registry_and_challenger_framework_gap.md`
  - strategy-family, metrics, and challenger work still missing
- `gaps/paper_trading_readiness_gap.md`
  - remaining gap between the current research/runtime engine and a credible paper-trading app
- `gaps/codex_watcher_and_autoresearch_gap.md`
  - missing watcher contract and autoresearch adapter surfaces for safe upgrade suggestions
- `gaps/execution_intent_gap.md`
  - the Stage 1 runtime-owner gap record, now kept as the closeout surface for `EXEC-001`
- `gaps/instrument_expansion_readiness_gap.md`
  - the widening ladder and readiness work for perps/futures
- `gaps/tmux_machine_law_and_packet_gap.md`
  - remaining machine-readable swarm-law work
- `issues/paper_runtime_blockers.md`
  - durable blockers that still prevent a truthful paper-runtime claim
- `issues/regime_shadow_corrective_slice.md`
  - historical corrective findings and guardrails for the condition and shadow lane after the first policy consumer landed
- `architecture/bootstrap_architecture.md`
  - current capture, feature, condition, and shadow architecture
- `runbooks/first_capture.md`
  - operator path for the first local capture run
- `runbooks/feature_condition_shadow_cycle.md`
  - operator path for the current feature -> condition -> shadow loop and failure triage
- `runbooks/ralph_tmux_swarm.md`
  - repo-local four-lane tmux/Ralph orchestration plus lane-health, mailbox, acceptance receipts, detached supervisor lifecycle, and continuous completion supervision
- `math/regime_shadow_modeling_contracts.md`
  - bounded mathematical and modeling contract for the current feature, regime, and shadow surfaces
- `math/market_regime_forecast_and_labeling_program.md`
  - canonical regime, direction-label, horizon, and evaluation-metric doctrine for future strategy work
- `math/strategy_family_registry.md`
  - first bounded strategy-family registry for repeated advisory challenger work
- `test/bootstrap_validation.md`
  - installed-deps validation commands, smoke procedures, and pytest coverage
- `examples/capture_run_report_example.qmd`
  - sample capture-run evidence packet
- `examples/proposal_example.qmd`
  - sample advisory improvement proposal packet
- `handoff/README.md`
  - doctrine for verbose human-readable continuation notes versus live `.ai/dropbox/` exchange
- `handoff/2026-04-12_bootstrap_phase_1.md`
  - historical receipt for the initial bootstrap pass
- `handoff/2026-04-18_agents_topology_and_handoff_doctrine.md`
  - focused receipt for the folder-level AGENTS topology and handoff-routing cleanup

## Routing Rules

- `docs/project/`
  - stable repo reality, ownership, and status surfaces
- `docs/task/`
  - active bounded execution surfaces
- `docs/prd/`
  - product requirements and milestone intent
- `docs/policy/`
  - runtime authority, governance, and promotion doctrine
- `docs/sdd/`
  - software and system design surfaces
- `docs/plans/`
  - planning synthesis, sequencing bridges, and roadmap surfaces
- `docs/issues/`
  - durable blockers, review findings, next-action tracking, and issue guides
- `docs/gaps/`
  - unresolved missing capability or known holes decomposed into staged gap docs
- `docs/architecture/`
  - current architecture and data-flow descriptions
- `docs/runbooks/`
  - operator procedures
- `docs/math/`
  - bounded mathematical, modeling, and experiment-contract guidance
- repo-local orchestration lives outside `docs/` in `.ai/`, `prd.json`, `progress.txt`, and `scripts/ralph/`
  - detached supervisor lifecycle also lives there through `scripts/agents/start_supervisor.sh`, `stop_supervisor.sh`, and `supervisor_status.sh`
  - finder modes also live there through `.ai/templates/architecture_finder.md`, `.ai/templates/research_finder.md`, and `.ai/dropbox/state/{finder_state.json,finder_decision.json}`
  - policy-only machine-readable swarm law also lives there through `.ai/swarm/{swarm.yaml,lane_rules.yaml,promotion_ladder.yaml}`
  - bounded research-stage machine law now also includes `.ai/swarm/{story_classes.yaml,metrics_registry.yaml,strategy_registry.yaml,instrument_scope.yaml}`
  - treat those as execution-control surfaces, not product or runtime authority
- `docs/test/`
  - validation notes and smoke checks
- `docs/handoff/`
  - verbose human continuation and operator handoff surfaces
  - never canonical story truth; handoff notes must point back to code, config, tests, `prd.json`, `progress.txt`, and the stable docs packet

Across all of these classes, writer should review the full docs surface on every
accepted loop and update every affected file category needed to keep repo truth
current.

## Which Surface Do I Use?

- Update `.ai/dropbox/` when the work needs live exchange, receipts, mailbox
  state, or machine-visible lane output.
- Update `docs/handoff/` when the slice needs a verbose human-readable resume
  note, operator context, or a durable continuation narrative.
- Update `prd.json`, `progress.txt`, code, config, schemas, tests, and the
  stable docs packet when the current repo truth changes.

## Reserved But Intentionally Absent In This Phase

- `docs/setup/`
  - deferred until Solana CLI or Anchor setup becomes an active implementation requirement
- `docs/hld/`, `docs/lld/`, `docs/done/`
  - reserved by `AGENTS.md`, but not populated yet in this slice
