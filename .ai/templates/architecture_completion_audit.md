# Defi-engine Architecture Completion Audit

You are running the final architecture audit for Defi-engine.

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
10. `docs/project/bootstrap_inventory.md`
11. `docs/runbooks/ralph_tmux_swarm.md`
12. current artifacts in `.ai/dropbox/research/`, `.ai/dropbox/build/`, `.ai/dropbox/architecture/`, and `.ai/dropbox/state/`

Your job:

- decide whether the repo still has a real missing design or implementation gap
- if yes, describe the gap in a way the writer-integrator can promote into `prd.json`
- if no, mark the audit clean

Required output:

- `.ai/dropbox/state/completion_audit_architecture.json`

The JSON must include:

- `status`: `clean | gaps_found`
- `gap_candidates`
- `rationale`
- `blocking_causes`
- `audited_at`

Do not update `prd.json`, `progress.txt`, or repo docs in this audit.
