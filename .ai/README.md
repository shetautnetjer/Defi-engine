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
- `docs/plans/strategy_descent_and_instrument_scope.md`
- `docs/math/market_regime_forecast_and_labeling_program.md`
- `docs/policy/runtime_authority_and_promotion_ladder.md`

The repo also carries a machine-readable governance layer under `.ai/swarm/`:

- `swarm.yaml`
- `lane_rules.yaml`
- `promotion_ladder.yaml`

In v1 these YAMLs are policy-only. They document packet rules, lane authority,
and promotion doctrine, but they do not override `prd.json`, `progress.txt`, or
the live supervisor scripts.

Lifecycle is intentionally split:

- `scripts/agents/start_swarm.sh`
  - tmux/session control only
- `scripts/agents/start_supervisor.sh`
  - detached continuous execution
- `scripts/agents/status_swarm.sh`
  - combined tmux + supervisor state
- `scripts/agents/stop_swarm.sh`
  - stops both tmux and the detached supervisor by default

The `dropbox/` subdirectories are tracked only for structure. Live lane output
inside them is ignored by Git unless explicitly staged.
