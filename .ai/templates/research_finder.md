# Defi-engine Research Finder

You are running research-finder inside the existing research lane.

Read, in order:

1. `AGENTS.md`
2. `.ai/agents/common.md`
3. `.ai/agents/research.md`
4. `.ai/index/current_repo_map.md`
5. `prd.json`
6. `progress.txt`
7. `.ai/dropbox/state/finder_state.json`
8. `.ai/dropbox/state/lane_health.md`
9. `.ai/dropbox/state/mailbox.jsonl`
10. current artifacts in `.ai/dropbox/research/`, `.ai/dropbox/build/`,
    `.ai/dropbox/architecture/`, and `.ai/dropbox/state/`

Read `.ai/dropbox/state/finder_state.json` first to determine the current finder
scope. Use the `pendingTrigger.scope` value as the output prefix. If the scope is
missing, stop and report that the finder trigger is malformed.

Your job:

- find missing evidence
- find stale assumptions
- find doctrine-vs-runtime mismatches
- find simpler or cheaper patterns already supported by repo truth or strong precedent
- stay evidence-first and repo-first
- output only evidence-backed findings and minimal follow-on story candidates
  when clearly justified

Required outputs:

- `.ai/dropbox/research/<scope>__research_gap_scan.md`
- `.ai/dropbox/research/<scope>__unknowns_and_needed_evidence.json`
- `.ai/dropbox/research/<scope>__followon_story_candidates.json`

Each finding should include:

- `finding_id`
- `claim`
- `why_current_evidence_is_insufficient`
- `evidence_checked`
- `missing_artifacts`
- `external_pattern_notes`
- `recommended_next_step`
- `proposed_story_id`

Do not update `prd.json`, `progress.txt`, repo docs, or runtime code.
