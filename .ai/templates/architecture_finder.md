# Defi-engine Architecture Finder

You are running architecture-finder inside the existing architecture lane.

Read, in order:

1. `AGENTS.md`
2. `AGENTS/engineering-flow.md`
3. `AGENTS/strategy-policy.md`
4. `AGENTS/trader-doctrine.md`
5. `.ai/agents/common.md`
6. `.ai/agents/architecture.md`
7. `.ai/index/current_repo_map.md`
8. `prd.json`
9. `progress.txt`
10. `.ai/dropbox/state/finder_state.json`
11. `.ai/dropbox/state/lane_health.md`
12. `.ai/dropbox/state/mailbox.jsonl`
13. current artifacts in `.ai/dropbox/research/`, `.ai/dropbox/build/`,
    `.ai/dropbox/architecture/`, and `.ai/dropbox/state/`

Read `.ai/dropbox/state/finder_state.json` first to determine the current finder
scope. Use the `pendingTrigger.scope` value as the output prefix. If the scope is
missing, stop and report that the finder trigger is malformed.

Your job:

- find duplicated truth surfaces
- find stale control-plane markers and state contradictions
- find liveness being mistaken for semantic completion
- find ceremony that should be collapsed, demoted, or deleted
- prefer subtraction before addition

Required outputs:

- `.ai/dropbox/architecture/<scope>__architecture_efficiency_audit.md`
- `.ai/dropbox/architecture/<scope>__subtraction_candidates.json`
- `.ai/dropbox/architecture/<scope>__followon_story_candidates.json`

Each finding should include:

- `finding_id`
- `title`
- `evidence`
- `severity`
- `type`
- `recommended_action`
- `subtract_or_build`
- `proposed_story_id`
- `acceptance_test`

Do not update `prd.json`, `progress.txt`, repo docs, or runtime code.
