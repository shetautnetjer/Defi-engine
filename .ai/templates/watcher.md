# Watcher Packet

Read `.ai/agents/common.md` before acting on this packet.

You are operating inside `{{REPO_ROOT}}`.

This watcher is **advisory-only** in v1.

## Trigger

- packet_id: `{{PACKET_ID}}`
- trigger_type: `{{TRIGGER_TYPE}}`
- canonical_story_id: `{{CANONICAL_STORY_ID}}`
- packet_dir: `{{PACKET_DIR}}`

## Observed Inputs

```json
{{OBSERVED_INPUTS_JSON}}
```

## Current Findings

{{FINDINGS_BULLETS}}

## Required Guardrails

- Do not mutate repo-tracked docs, code, tests, `prd.json`, or `progress.txt`.
- Treat `prd.json.activeStoryId` as canonical story truth.
- Treat `.ai/dropbox/state/*` control-plane receipts as supporting evidence, not authority.
- If the packet says `truth_drift`, stop after writing the review packet and recommendation.
- If sandbox eval commands ran, treat their outputs as advisory receipts only.
- Recommend routes into `docs/issues/`, `docs/gaps/`, `docs/plans/`, or `docs/task/`, but do not create or edit those tracked files in v1.

## Output

Write only bounded watcher evidence:

- `review.qmd`
- `summary.json`

Recommended route: `{{RECOMMENDED_ROUTE}}`

## Packet Summary JSON

```json
{{SUMMARY_JSON}}
```
