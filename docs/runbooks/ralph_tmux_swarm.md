# Ralph TMux Swarm

This runbook describes the repo-local four-lane Ralph/tmux workflow for
`Defi-engine`.

## Purpose

Use this workflow when the work is long-horizon, story-driven, and easier to
understand with fixed lane roles than with one large undifferentiated agent.

The current intended target for this workflow is receipt-backed follow-on runtime
hardening after the first source-owner, settlement-owner, and realized-feedback slices:

- execution-intent routing between `risk/` and `settlement/`

The longer north-star target is a paper-first, Solana-first crypto backtesting
and paper-trading platform that classifies direction and regimes, compares
strategies under explicit policy/risk/settlement governance, and widens into
Jupiter perps and Coinbase futures only through governed capability stages.

The active repo discipline is Stage 1 current-truth consolidation:

- keep the entire `docs/` tree current as accepted work lands
- keep `prd.json`, `progress.txt`, and docs truth aligned
- let writer-integrator continuously route contradictions into `docs/issues/`,
  missing capability into `docs/gaps/`, and only the best next receipt-backed
  stories into `prd.json`
- prefer rich status and clean terminal state over fake liveness

## Required packet

Before a lane widens backlog truth, it should read this packet:

- `AGENTS.md`
- `.ai/agents/common.md`
- `.ai/index/current_repo_map.md`
- `prd.json`
- `progress.txt`
- `docs/project/current_runtime_truth.md`
- `docs/prd/crypto_backtesting_mission.md`
- `docs/prd/backtesting_completion_definition.md`
- `docs/issues/governed_product_descent_capability_ladder.md`
- `docs/project/bootstrap_inventory.md`
- `docs/issues/paper_runtime_blockers.md`
- `docs/sdd/d5_trading_engine_sdd.md`
- `docs/math/regime_shadow_modeling_contracts.md`
- `docs/math/market_regime_forecast_and_labeling_program.md`
- `docs/policy/runtime_authority_and_promotion_ladder.md`
- `docs/policy/writer_story_promotion_rubric.md`
- `docs/plans/strategy_descent_and_instrument_scope.md`
- `docs/runbooks/feature_condition_shadow_cycle.md`

The repo also carries a machine-readable swarm governance packet:

- `.ai/swarm/swarm.yaml`
- `.ai/swarm/lane_rules.yaml`
- `.ai/swarm/promotion_ladder.yaml`

In v1 this `.ai/swarm/` layer is policy-only. It documents packet rules, lane
authority, and promotion doctrine, but it does not override `prd.json`,
`progress.txt`, or the live supervisor scripts.

## Story truth

The canonical story ledger is:

- `prd.json`
- `progress.txt`

The current active story is `activeStoryId` in `prd.json`.

Top-level swarm completion truth also lives in `prd.json`:

- `swarmState`
  - `active`
  - `blocked`
  - `backlog_exhausted`
  - `audit_followons_present`
  - `terminal_complete`
- `completionAuditState`
  - `pending`
  - `running`
  - `clean`
  - `gaps_promoted`

The writer-integrator lane is the only lane that may:

- advance `prd.json`
- append `progress.txt`
- treat docs changes as accepted repo truth
- complete the repo-wide docs-truth reconciliation for an accepted story
- mine accepted proposals from the docs surface and receipts to decide the next
  bounded stories

## Lane roles

1. research
   - `research-skill`
   - `exa-search-skill`
   - `crawl4ai-skill`
2. builder
   - ChatGPT 5.4 default
   - `jetbrains-mcp`
3. architecture
   - `jetbrains-skill`
   - `jetbrains-mcp`
4. writer-integrator
   - `ralph`
   - `ralph-loop`
   - docs/state owner

No new permanent lanes are added. Finder work happens inside trusted lanes:

- `architecture-finder`
  - subtraction-first audit mode inside the architecture lane
- `research-finder`
  - evidence-first audit mode inside the research lane

## Shared handoff

Lane exchange lives in `.ai/dropbox/`.

Subdirectories:

- `research/`
- `build/`
- `architecture/`
- `state/`

This is working exchange, not canonical long-term truth.

Runtime supervision receipts are created under `.ai/dropbox/state/`:

- `lane_health.md`
- `lane_health.json`
- `mailbox.jsonl`
- `mailbox_current.json`
- `finder_state.json`
- `finder_decision.json`
- `docs_truth_receipt.json`
- `docs_sync_status.json`
- `story_promotion_receipt.json`
- `accepted_receipts/*.json`
- `runtime/*` launch, active, and completion markers
- `completion_audit_*.json`

Finder-mode outputs:

- architecture finder:
  - `<scope>__architecture_efficiency_audit.md`
  - `<scope>__subtraction_candidates.json`
  - `<scope>__followon_story_candidates.json`
- research finder:
  - `<scope>__research_gap_scan.md`
  - `<scope>__unknowns_and_needed_evidence.json`
  - `<scope>__followon_story_candidates.json`

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

`start_swarm.sh` is session control only. It prepares tmux, lane titles, and the
watch window. It does not auto-start detached continuous supervision.

## Start continuous supervision

Once the session exists, start the detached supervisor separately:

```bash
./scripts/agents/start_supervisor.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

This is the canonical “continue without interruption” entrypoint. It runs the
continuous completion loop in the background, writes PID / launch / heartbeat /
last-exit receipts under `.ai/dropbox/state/runtime/`, and keeps story progress
moving until the ledger is exhausted and the final audits are clean.

## Common commands

Status:

```bash
./scripts/agents/status_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Detached supervisor status only:

```bash
./scripts/agents/supervisor_status.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Refresh the watch dashboard on an existing session:

```bash
./scripts/agents/refresh_watch_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Refresh health directly:

```bash
./scripts/agents/health_swarm.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Relaunch the highest-priority stale lane safely:

```bash
./scripts/agents/relaunch_stale_lanes.sh --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine
```

Run the continuous completion supervisor directly:

```bash
./scripts/agents/run_persistent_cycle.sh \
  --repo /home/netjer/Projects/AI-Frame/Brain/Defi-engine \
  --interval 60
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

`stop_swarm.sh` stops both the detached supervisor and the tmux session. Use it
as the default “stop everything” command.

## Acceptance discipline

Every story loop should follow this order:

1. writer-integrator confirms the active story
2. research gathers evidence
3. architecture reviews the cleanest path
4. builder implements the bounded slice
5. writer-integrator writes a structured acceptance receipt
6. writer-integrator accepts, rejects, blocks, or escalates
7. only after receipt-backed acceptance or escalation:
   - update `prd.json`
   - append `progress.txt`
   - update affected docs after a repo-wide docs-truth scan across `docs/`
   - optionally create a commit if the slice is accepted, validated, and the
      writer-integrator can tie the commit to the story id and receipt id

Blocked stories enter recovery rather than stopping the swarm immediately:

1. research re-checks likely root causes
2. architecture re-evaluates the design path
3. builder attempts the bounded repair
4. writer-integrator decides again

Recovery continues until architecture marks the path exhausted in
`<story-id>__decision.json`, at which point writer-integrator must escalate or
promote a replacement gap story.

## Persistent supervision

The lanes are still one-shot Codex runs. They launch, do work, write artifacts,
and return to shell. Persistent operation comes from supervision, not daemon
workers.

Use the repo-local control loop to avoid confusing “pane exists” with “lane is
healthy”:

1. `health_swarm.sh`
   - inspects pane command state, expected artifact freshness, and launch
     markers
   - refreshes `lane_health.md` and `lane_health.json`
2. `relaunch_stale_lanes.sh`
   - restarts the highest-priority lane that is stale or failed
   - also launches the rightful next idle lane for the active story once
     upstream completion markers prove the previous step finished, even if that
     upstream lane did not emit fresh story-scoped artifacts
   - keeps downstream lanes from restarting ahead of fresh upstream outputs
3. `start_supervisor.sh`
   - launches the detached `run_persistent_cycle.sh` loop
   - no-ops if a healthy supervisor is already running
4. `run_persistent_cycle.sh`
   - loop engine behind the detached supervisor
   - keeps cycling until there are no eligible stories left in `prd.json`
   - then runs the final architect + writer completion audit before stopping

The mailbox is an append-only notification surface. It does not advance story
truth by itself. Research systems may propose and compare, but they remain
advisory until the promotion ladder says otherwise.
truth. Writer-integrator still owns acceptance.

Use `mailbox_current.json` for the compacted current-notification view.
`mailbox.jsonl` remains the raw append-only log.

The story ledger now uses explicit states:

- `ready`
- `active`
- `recovery`
- `blocked_external`
- `deferred`
- `done`
- `escalated`

`status_swarm.sh` should be read across four dimensions:

- detached supervisor state
- `alive`
- `producing`
- `accepted`

Terminal completion is stricter than “no eligible stories remain.” The loop is
only terminally complete when:

- no eligible stories remain
- architecture completion audit is clean or audit-known only
- writer completion audit is clean or audit-known only
- no writer-pending finder promotions remain

If completion or finder audits discover real follow-ons, the swarm should
resolve to `audit_followons_present` until writer-integrator promotes, defers,
rejects, or marks those candidates audit-known.

## Watch window

The repo-local watch window is retuned after startup so it reflects the
supervision model instead of the older bootstrap observer view.

Watch panes:

1. `git-status`
2. `git-diff-stat`
3. `lane-health`
4. `swarm-events`

`lane-health` continuously refreshes `lane_health.md` without writing mailbox
events, and `swarm-events` tails the mailbox, the tmux lane activity log, and
the detached supervisor log.

## Current safe framing

Do not use this workflow to imply that Defi-engine already has a governed paper
runtime.

The repo still truthfully remains:

- source truth
- bounded features
- bounded condition
- explicit policy traces
- explicit risk gate
- explicit paper settlement
- bounded shadow

Future stories should now come from real blocker notes and receipt-backed gaps,
not from the old assumption that `settlement/` is still missing.
