# Training Automation

This folder adapts the small event-driven automation pack from
`defi_codex_automation_pack_v2` into the repo-owned training surface.

Use it to watch a JSONL queue, render bounded prompts, and dispatch
`codex exec --json` or an equivalent CLI mode over already-written receipts.

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

- tmux/supervisor owns long-running hydration and incremental collection
- `codex exec --json -C <repo>` owns bounded semantic review work
- QMD is the rich evidence packet
- small JSON files remain queue and heartbeat contracts only

Future-phase note:

- the official Codex automation surfaces now include non-interactive mode,
  app-server, and MCP server docs
- this repo is intentionally deferring an app-server / exec-server control-plane
  redesign until the current event schema, receipt layout, and trading harness
  prompts are stable
- keep watching the Codex changelog before widening the automation topology:
  https://developers.openai.com/codex/changelog
