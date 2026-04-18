# Handoff Notes

`docs/handoff/` is the durable human-readable continuation surface for
Defi-engine.

Use this directory when a bounded slice needs:

- a verbose resume note for the next engineer or agent
- operator-facing continuation context
- a historical closeout record that explains what changed and what to do next

Do not treat handoff notes as canonical truth by themselves. Every handoff here
should point back to:

- `prd.json`
- `progress.txt`
- current code, config, schemas, and tests
- `docs/project/current_runtime_truth.md`
- any other stable docs packet that now reflects the accepted result

Recommended handoff structure:

1. status and scope of the completed slice
2. what is now true
3. exact validation or checks run
4. open risks or deferred gaps
5. next recommended seam

Use `.ai/dropbox/` for live working exchange and receipts during active work.
Use `docs/handoff/` after the slice is complete and the next reader needs a
clear human narrative.
