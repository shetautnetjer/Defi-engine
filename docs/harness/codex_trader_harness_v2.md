# Codex Trader Harness V2

## Purpose

Define the persistent Codex `trader` lane as a governed research-and-engineering harness for D5/Defi-engine.

The `trader` lane is not a live trader. It is a persistent reviewer, experiment proposer, bounded patcher, and evidence synthesizer.

## Mission

Make the trading engine better by converting SQL/QMD/JSON evidence into bounded candidate experiments.

## Authority

The `trader` lane may:

- inspect repo truth
- inspect SQL/QMD/JSON evidence
- summarize failures
- propose candidate overlays
- run bounded research tasks
- patch scoped research/training utilities
- write receipts

The `trader` lane may not:

- place live trades
- sign transactions
- weaken risk controls
- mutate runtime policy without explicit task scope
- self-promote a candidate
- treat memory/Notion as runtime authority

## Truth Hierarchy

1. SQL canonical truth
2. JSON/JSONL receipts and schemas
3. QMD reports generated from SQL
4. repo code/config/tests/docs
5. Notion summaries
6. memory/hindsight
7. prior Codex transcript context

## Lanes

### Persistent `trader`

Use for:

- paper session review
- experiment review
- condition/regime review
- failure-family ranking
- evidence rollup
- candidate batch design

### Fresh `task`

Use for:

- failing tests
- docs sync
- schema addition
- one-shot repair
- bounded implementation tasks

## Core Loop

```text
event
→ read repo truth
→ read SQL/QMD/JSON evidence
→ classify failure family
→ propose bounded candidate batch
→ write receipt
→ stop
```

## Required Output Shape

Every non-trivial trader turn must produce:

- `run_id`
- `target_surface`
- `baseline_refs`
- `evidence_refs`
- `failure_family`
- `selected_batch_type`
- `falsification_candidate`
- `decision`
- `next_action`

## Default Decision Values

- `NO_ACTION`
- `PROPOSE_BATCH`
- `REQUEST_DATA_REPAIR`
- `REQUEST_FEATURE_REPAIR`
- `SHADOW_ONLY`
- `KEEP_FOR_REVIEW`
- `REJECT`
