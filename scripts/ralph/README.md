# Defi-engine Ralph Runner

This is the repo-local Ralph loop surface for Defi-engine.

It is intentionally biased toward the writer-integrator role:

- read `prd.json`
- read `progress.txt`
- inspect active dropbox outputs
- update accepted state
- keep docs and repo truth aligned

The canonical execution command is:

```bash
./scripts/ralph/ralph.sh --tool codex 1
```

Or inside a tmux-lanes session:

```bash
/home/netjer/Projects/AI-Frame/muscles/skills/tmux-lanes/scripts/tmux_lanes_run_ralph.sh \
  --repo /abs/path/to/Defi-engine \
  --lane 4 \
  --tool codex \
  --max-iterations 1
```
