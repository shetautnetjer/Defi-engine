# Docs Index

This directory is the repo-local routing map for documentation in `Defi-engine`.

Code, config, schema, and checks remain the runtime authority. These docs explain the current repo state, the active execution slice, and the deferred gaps without claiming unimplemented behavior.

## Current Documents

- `project/bootstrap_inventory.md`
  - stable snapshot of what is implemented, scaffolded, and missing
- `prd/d5_trading_engine_prd.md`
  - repo-local product requirements for the paper-first source, feature, condition, and shadow surface
- `sdd/d5_trading_engine_sdd.md`
  - current software design for the source-truth stack plus bounded feature, condition, and shadow owners
- `task/ingest_hardening_phase_1.md`
  - completed hardening slice that made the bootstrap ingest contracts truthful
- `task/source_expansion_preconditions.md`
  - active bounded execution surface for mint-locked universe expansion without bypassing downstream contracts
- `task/continuous_capture_ownership.md`
  - bounded next slice for freshness, completeness, and operator-visible source ownership
- `task/first_feature_input_contract.md`
  - first post-ingest contract that defines which canonical truth the feature layer may consume
- `task/global_regime_condition_and_shadow_stack.md`
  - first real condition scorer plus the bounded shadow-only meta-stack and experiment receipts
- `plans/source_expansion_preconditions.md`
  - near-term sequencing for Jupiter → Helius → Coinbase source expansion
- `plans/historical_research_protocol.md`
  - future Massive-driven research and walk-forward protocol
- `plans/build_sequence_and_runtime_ownership.md`
  - bridge note from source-ingest bootstrap into downstream runtime layer ownership
- `plans/source_map_and_source_completeness.md`
  - provider-role map and source-completeness doctrine before downstream runtime dependence
- `gaps/bootstrap_gap_register.md`
  - deferred or missing capabilities that should not be treated as shipped
- `issues/paper_runtime_blockers.md`
  - durable blockers that still prevent a truthful paper-runtime claim
- `issues/regime_shadow_corrective_slice.md`
  - corrective findings for the current condition and shadow lane before policy work should consume them
- `architecture/bootstrap_architecture.md`
  - current capture, feature, condition, and shadow architecture
- `runbooks/first_capture.md`
  - operator path for the first local capture run
- `runbooks/feature_condition_shadow_cycle.md`
  - operator path for the current feature -> condition -> shadow loop and failure triage
- `runbooks/ralph_tmux_swarm.md`
  - repo-local four-lane tmux/Ralph orchestration for long-horizon, story-driven work
- `math/regime_shadow_modeling_contracts.md`
  - bounded mathematical and modeling contract for the current feature, regime, and shadow surfaces
- `test/bootstrap_validation.md`
  - installed-deps validation commands, smoke procedures, and pytest coverage
- `handoff/2026-04-12_bootstrap_phase_1.md`
  - historical receipt for the initial bootstrap pass

## Routing Rules

- `docs/project/`
  - stable repo reality, ownership, and status surfaces
- `docs/task/`
  - active bounded execution surfaces
- `docs/prd/`
  - product requirements and milestone intent
- `docs/sdd/`
  - software and system design surfaces
- `docs/plans/`
  - planning synthesis, sequencing bridges, and roadmap surfaces
- `docs/issues/`
  - durable blockers, review findings, and next-action tracking
- `docs/gaps/`
  - unresolved missing capability or known holes
- `docs/architecture/`
  - current architecture and data-flow descriptions
- `docs/runbooks/`
  - operator procedures
- `docs/math/`
  - bounded mathematical, modeling, and experiment-contract guidance
- repo-local orchestration lives outside `docs/` in `.ai/`, `prd.json`, `progress.txt`, and `scripts/ralph/`
  - treat those as execution-control surfaces, not product or runtime authority
- `docs/test/`
  - validation notes and smoke checks
- `docs/handoff/`
  - historical handoff and receipt surfaces

## Reserved But Intentionally Absent In This Phase

- `docs/setup/`
  - deferred until Solana CLI or Anchor setup becomes an active implementation requirement
- `docs/hld/`, `docs/lld/`, `docs/done/`
  - reserved by `AGENTS.md`, but not populated yet in this slice
