# Defi-engine Agent Orchestration

This directory is the repo-local control surface for Ralph-style tmux work in
`Defi-engine`.

It is intentionally split into four concerns:

- `agents/`
  - lane-specific guidance derived from repo doctrine
- `index/`
  - current repo truth so lanes do not invent already-existing surfaces
- `templates/`
  - lane prompt files for `codex exec` or other lane launchers
- `dropbox/`
  - shared handoff area for live lane outputs
  - runtime-created health, mailbox, runtime, and acceptance receipts under `dropbox/state/`

The canonical story ledger does **not** live in this directory.

- `prd.json`
  - active story ledger
- `progress.txt`
  - append-only carry-forward state

Use the surfaces deliberately:

- `.ai/dropbox/`
  - live working exchange, receipts, runtime status, mailbox, and machine-visible handoff state
- `docs/handoff/`
  - verbose human-readable continuation notes after a bounded slice is complete
- `prd.json` / `progress.txt`
  - canonical story and carry-forward truth

The swarm now runs as a continuous completion loop:

- bounded one-shot lanes under a persistent supervisor
- explicit story states in `prd.json`
- receipt-backed acceptance under `dropbox/state/accepted_receipts/`
- final architect + writer completion audit before the loop is allowed to stop
- no new permanent lanes; `architecture-finder` and `research-finder` run as
  mode switches inside the existing architecture and research lanes
- top-level swarm completion truth in `prd.json` via `swarmState` and
  `completionAuditState`

The north-star packet the swarm should read before widening backlog truth now
also includes:

- `docs/project/current_runtime_truth.md`
- `docs/prd/crypto_backtesting_mission.md`
- `docs/prd/backtesting_completion_definition.md`
- `docs/issues/governed_product_descent_capability_ladder.md`
- `docs/gaps/bootstrap_gap_register.md`
- `docs/plans/strategy_descent_and_instrument_scope.md`
- `docs/math/market_regime_forecast_and_labeling_program.md`
- `docs/policy/runtime_authority_and_promotion_ladder.md`

The repo also carries a machine-readable governance layer under `.ai/swarm/`:

- `swarm.yaml`
- `lane_rules.yaml`
- `promotion_ladder.yaml`
- `doc_owners.yaml`
- `story_classes.yaml`
- `metrics_registry.yaml`
- `strategy_registry.yaml`
- `instrument_scope.yaml`
- `watcher.yaml`

In v1 these YAMLs are still policy-first. They now also define the bounded
research proposal-review envelope for `LABEL-*` / `STRAT-*`, but they still do
not override runtime authority or replace `prd.json`, `progress.txt`, or the
live supervisor scripts.

Treat the `.ai/swarm/` YAML layer as policy-only machine law: it shapes lane
behavior and research backlog movement, but it is not runtime authority by
itself.

The repo also carries a machine-readable research profile pack:

- `.ai/profiles.toml`
  - training and autoresearch bias profiles only
- `.ai/schemas/profile.schema.json`
  - validation schema for the profile pack
- `.ai/policies/profile_router_policy.v1.json`
  - thin profile-governor routing weights and thresholds
- `.ai/schemas/meta_governor_scorecard.schema.json`
  - scorecard schema for governor review output
- `.ai/schemas/profile_router_policy.schema.json`
  - validation schema for the router policy
- `.ai/schemas/profile_governor_decision.schema.json`
  - validation schema for governor actions and reasons
- `.ai/prompts/profile_governor_turn.md`
  - companion prompt surface for the governor review layer

These profiles shape what the trader/autoresearch lane prefers to explore and
how it ranks evidence. They do **not** grant runtime authority and they do not
replace strategy policy, risk policy, or live execution controls.

The profile governor is a thin review/router overlay only. It consumes existing
proposal, comparison, SQL, and QMD evidence and can recommend actions like
select, blend, shadow, or need-more-evidence, but it does not replace runtime
policy or risk authority.

Lifecycle is intentionally split:

- `scripts/agents/start_swarm.sh`
  - tmux/session control only
- `scripts/agents/start_supervisor.sh`
  - detached continuous execution
- `scripts/agents/start_watch_adapter.sh`
  - standalone advisory watcher loop
- `scripts/agents/status_swarm.sh`
  - combined tmux + supervisor state
- `scripts/agents/status_watch_adapter.sh`
  - standalone watcher lock and packet state
- `scripts/agents/stop_swarm.sh`
  - stops both tmux and the detached supervisor by default

The watcher is deliberately separate from the persistent supervisor in v1:

- advisory-only
- no repo-tracked mutations
- `prd.json.activeStoryId` is canonical over stale dropbox state
- single-run lock at `.ai/dropbox/state/watcher.lock`
- bounded sandbox evals only when `--sandbox-evals` is passed
- watcher evidence lands in `data/reports/watcher/`
- archive copies of ignored `.ai/dropbox` residue land in `data/archive/ai_dropbox/`

Watcher prompt and runtime surfaces:

- `.ai/templates/watcher.md`
- `scripts/agents/codex_watch_adapter.py`
- `scripts/agents/audit_ai_surfaces.py`
- `.ai/dropbox/state/watcher_state.json`
- `.ai/dropbox/state/watcher_latest.json`

The `dropbox/` subdirectories are tracked only for structure. Live lane output
inside them is ignored by Git unless explicitly staged.

Treat `.ai/dropbox/` as active exchange, not as a substitute for stable docs or
canonical story state. When a slice needs a durable human handoff, write that
under `docs/handoff/` and point it back to the current runtime-truth packet.

The bounded research review packet now has three durable surfaces:

- `improvement_proposal_v1`
  - proposal truth for advisory next-test packets
- `proposal_review_v1`
  - deterministic review truth for proposal decisions
- `.ai/dropbox/state/research_proposal_review_receipt.json`
  - latest review receipt for swarm/status visibility

Operators can refresh that packet explicitly with:

- `d5 review-proposal <proposal_id>`

This review flow is advisory-only. It does not grant runtime authority or edit
`prd.json`, `progress.txt`, policy, risk, or runtime config by itself.

The bounded proposal-priority packet now adds four more durable surfaces:

- `proposal_comparison_v1`
  - comparison-run truth for reviewed proposals
- `proposal_comparison_item_v1`
  - ranked candidate truth with score breakdowns
- `proposal_supersession_v1`
  - append-only same-kind supersession history
- `.ai/dropbox/state/research_proposal_priority_receipt.json`
  - latest bounded next-test selection receipt

Operators can refresh that packet explicitly with:

- `d5 compare-proposals`

This comparison flow is also advisory-only. It may choose the next bounded
experiment, but it does not grant runtime authority or edit `prd.json`,
`progress.txt`, policy, risk, or runtime config by itself.

The shadow research packet also includes a bounded regime-model comparison lane:

- `d5 run-shadow regime-model-compare-v1`
- `experiment_run` with `experiment_name = regime_model_compare_v1`
- `data/research/regime_model_compare/<run_id>/comparison.json`
- advisory-only `regime_model_compare_follow_on` proposal packets

That lane may compare HMM, GMM, and an optional `statsmodels` candidate on the
existing canonical 15-minute feature truth, but it does not grant runtime
authority or mutate policy, risk, execution, settlement, or runtime config.
