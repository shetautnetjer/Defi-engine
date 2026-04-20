# Training Automation

This folder adapts the small event-driven automation pack from
`defi_codex_automation_pack_v2` into the repo-owned training surface.

Use it to watch a JSONL queue, render bounded prompts, and dispatch
`codex exec --json` or `codex exec resume` over already-written receipts.

The automation layer is intentionally thin:

- it watches events
- it renders prompts
- it dispatches Codex
- it writes receipts and logs

It does not replace the engine. SQL truth, JSON artifacts, and QMD reports must
already exist before an event is emitted here.

The watcher should treat the local trading doctrine as required context:

- `AGENTS.md`
- `training/AGENTS.md`
- `training/trading_agent_harness.md`
- `training/program.md`
- `training/rubrics/training_regime_rubric.md`
- `docs/task/trading_qmd_report_contract.md`

Event JSON should stay thin and point back to SQL truth plus QMD evidence.

The intended split is:

- `training/automation/bin/training_supervisor.py` owns long-running hydration,
  selected-regimen bootstrap, incremental collection, review, and one-iteration
  paper loops from tmux
- the named persistent `trader` lane owns resumed paper-session, experiment,
  and condition review continuity
- the fresh `task` lane owns one-shot feature review and repair-style runs
- `codex exec --json -C <repo>` owns fresh bounded semantic work
- `codex exec resume <SESSION_ID> --json` owns the persistent trader lane
- QMD is the rich evidence packet
- small JSON files remain queue and heartbeat contracts only

Lane continuity is tracked under:

- `training/automation/state/lane_sessions.json`
- `training/automation/state/watcher_status.json`

The watcher now also acts like the light session steward for the automation lane:

- it tails the thin event queue
- it dispatches fresh or resumed Codex runs
- it writes `watcher_status.json` so `d5 training status --json` can surface
  trader-lane health next to source-collection and paper-practice receipts

Start or restart the continuous paper-training steward with:

```bash
ATTACH=0 training/automation/tmux/start_training_supervisor_tmux.sh
```

This steward follows the selected training regimen readiness from
`d5 training status --json`. A partial 730-day Massive cache can keep trying to
heal in the background, but it must not block `quickstart_300d` once the
required 300-day ladder is ready.

Repo-local Codex config and hooks live under:

- `.codex/config.toml`
- `.codex/hooks.json`

Future-phase note:

- the official Codex automation surfaces now include non-interactive mode,
  app-server, and MCP server docs
- this repo is intentionally deferring an app-server / exec-server control-plane
  redesign until the current event schema, receipt layout, and trading harness
  prompts are stable
- keep watching the Codex changelog before widening the automation topology:
  https://developers.openai.com/codex/changelog
