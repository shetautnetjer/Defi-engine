# Ralph TMux Swarm

This runbook describes the repo-local four-lane Ralph/tmux workflow for
`Defi-engine`.

## Purpose

Use this workflow when the work is long-horizon, story-driven, and easier to
understand with fixed lane roles than with one large undifferentiated agent.

The current intended target for this workflow is the still-missing runtime
owners:

- `policy/`
- `risk/`
- `settlement/`

## Story truth

The canonical story ledger is:

- `prd.json`
- `progress.txt`

The current active story is `activeStoryId` in `prd.json`.

The writer-integrator lane is the only lane that may:

- advance `prd.json`
- append `progress.txt`
- treat docs changes as accepted repo truth

## Lane roles

1. research
   - `research-skill`
   - `exa-search-skill`
   - `crawl4ai-skill`
2. builder
   - Codex Spark preferred
   - `jetbrains-mcp`
3. architecture
   - `jetbrains-skill`
   - `jetbrains-mcp`
4. writer-integrator
   - `ralph`
   - `ralph-loop`
   - docs/state owner

## Shared handoff

Lane exchange lives in `.ai/dropbox/`.

Subdirectories:

- `research/`
- `build/`
- `architecture/`
- `state/`

This is working exchange, not canonical long-term truth.

## Start the session

```bash
./scripts/agents/start_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Optional auto-launch of all four lanes:

```bash
./scripts/agents/start_swarm.sh \
  --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine \
  --launch-all
```

## Common commands

Status:

```bash
./scripts/agents/status_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Launch one lane run:

```bash
./scripts/agents/send_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine --lane research --run
./scripts/agents/send_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine --lane builder --run
./scripts/agents/send_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine --lane architecture --run
./scripts/agents/send_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine --lane writer --run
```

Run the writer-integrator Ralph loop in lane 4:

```bash
/home/netjer/Projects/AI-Frame/muscles/skills/tmux-lanes/scripts/tmux_lanes_run_ralph.sh \
  --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine \
  --lane 4 \
  --tool codex \
  --max-iterations 1
```

Capture session state:

```bash
./scripts/agents/capture_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Stop:

```bash
./scripts/agents/stop_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

## Acceptance discipline

Every loop should follow this order:

1. writer-integrator confirms the active story
2. research gathers evidence
3. architecture reviews the cleanest path
4. builder implements the bounded slice
5. writer-integrator accepts or rejects
6. only after acceptance:
   - update `prd.json`
   - append `progress.txt`
   - update affected docs

## Current safe framing

Do not use this workflow to imply that Defi-engine already has a governed paper
runtime.

The repo still truthfully remains:

- source truth
- bounded features
- bounded condition
- bounded shadow

The next missing runtime owners are still `policy/`, `risk/`, and
`settlement/`.
