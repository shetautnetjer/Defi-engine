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
