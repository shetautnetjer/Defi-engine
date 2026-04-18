# Dropbox

This is the shared handoff area for the Defi-engine Ralph/tmux swarm.

Tracked here:

- the folder structure
- placeholder files only

Ignored by Git here:

- live lane outputs during active work

Subdirectories:

- `research/`
- `build/`
- `architecture/`
- `state/`

Runtime-created state receipts under `state/`:

- `lane_health.md`
- `lane_health.json`
- `mailbox.jsonl`
- `mailbox_current.json`
- `finder_state.json`
- `finder_decision.json`
- `accepted_receipts/*.json`
- `watcher_state.json`
- `watcher_latest.json`
- `watcher.lock`
- `runtime/*` lane launch, active, and completion markers
- `runtime/persistent_cycle.pid`
- `runtime/persistent_cycle.log`
- `runtime/persistent_cycle_launch.json`
- `runtime/persistent_cycle_heartbeat.json`
- `runtime/persistent_cycle_last_exit.json`
- `completion_audit_*.json`
- `research_proposal_review_receipt.json`
- `research_proposal_priority_receipt.json`

Naming convention:

- `<story-id>__brief.md`
- `<story-id>__doc_refs.json`
- `<story-id>__delivery.md`
- `<story-id>__review.md`

The writer-integrator lane owns accepted state and should treat this directory
as working exchange, not canonical long-term truth.

Use this directory for:

- live lane outputs
- receipt packets
- mailbox and runtime state
- machine-visible handoff during active work

Do **not** use this directory as the durable human resume note. Put that in
`docs/handoff/` once the bounded slice is complete, and keep `prd.json`,
`progress.txt`, code, config, tests, and stable docs as canonical truth.

The detached supervisor is a control-plane process, not a canonical truth
owner. Its receipts prove liveness and loop progress only.

The standalone watcher is also control-plane only:

- it is advisory-only in v1
- it must treat `prd.json.activeStoryId` as canonical story truth
- it writes JSON and QMD review packets under `data/reports/watcher/`
- it may copy ignored `.ai/dropbox` residue into `data/archive/ai_dropbox/`
- it must not mutate repo-tracked docs, code, tests, `prd.json`, or `progress.txt`

Mailbox is a notification surface, not canonical memory. `mailbox_current.json`
is the compacted current view; `mailbox.jsonl` remains the append-only raw log.

Finder-mode artifacts are advisory until writer-integrator promotes or defers
them explicitly:

- architecture finder:
  - `<scope>__architecture_efficiency_audit.md`
  - `<scope>__subtraction_candidates.json`
  - `<scope>__followon_story_candidates.json`
- research finder:
  - `<scope>__research_gap_scan.md`
  - `<scope>__unknowns_and_needed_evidence.json`
  - `<scope>__followon_story_candidates.json`
