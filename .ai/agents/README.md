# Lane Guides

These files are the repo-local agent pack for the Defi-engine Ralph/tmux swarm.

Reading order for any lane:

1. `AGENTS.md`
2. relevant `AGENTS/*.md` playbooks
3. `.ai/agents/common.md`
4. the lane-specific file in this directory
5. `.ai/index/current_repo_map.md`
6. `prd.json`
7. `progress.txt`

Lane files:

- `research.md`
- `builder.md`
- `architecture.md`
- `writer_integrator.md`

The writer-integrator lane is the only lane that may advance `prd.json`,
append `progress.txt`, or treat docs updates as accepted repo truth.
