# Training Automation

This folder adapts the small event-driven automation pack from
`defi_codex_automation_pack_v2` into the repo-owned training surface.

Use it to watch a JSONL queue, render bounded prompts, and dispatch
`codex --exec` or an equivalent CLI mode over already-written receipts.

The automation layer is intentionally thin:

- it watches events
- it renders prompts
- it dispatches Codex
- it writes receipts and logs

It does not replace the engine. SQL truth, JSON artifacts, and QMD reports must
already exist before an event is emitted here.
