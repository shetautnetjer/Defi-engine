# Defi-engine Writer Completion Audit

You are running the final writer-integrator completion audit for Defi-engine.

Read, in order:

1. `AGENTS.md`
2. `AGENTS/engineering-flow.md`
3. `AGENTS/strategy-policy.md`
4. `AGENTS/trader-doctrine.md`
5. `.ai/agents/common.md`
6. `.ai/agents/writer_integrator.md`
7. `.ai/index/current_repo_map.md`
8. `prd.json`
9. `progress.txt`
10. `.ai/dropbox/state/completion_audit_architecture.json`
11. `.ai/dropbox/state/finder_state.json`
12. current artifacts in `.ai/dropbox/state/`

Your job:

- if architecture found a real missing gap, promote it into `prd.json` with `./scripts/agents/promote_gap_story.sh`
- if completion-scope finder outputs exist, consume them before deciding whether a follow-on should be promoted, deferred, rejected, or marked audit-known only
- if you promote a new gap, append `progress.txt` with the new story id and reason
- if there is no real missing gap, record a clean completion audit
- if a follow-on is real but should remain audit-known only, record that explicitly without reopening the backlog

Required output:

- `.ai/dropbox/state/completion_audit_writer.json`

The JSON must include:

- `audit_id`
- `status`: `clean | gap_promoted | audit_known_only`
- `promoted_story_ids`
- `deferred_story_ids`
- `rationale`
- `audited_at`

Do not weaken standards just to stop the loop.
