# Codex Watcher And Autoresearch Adapter Gap

## Stage

Stage 3 through Stage 5: label truth, strategy research, and governed
promotion, with an orchestration support seam in the current packet.

## Current truth

The repo already has a meaningful watch surface:

- `prd.json`
- `progress.txt`
- `.ai/dropbox/state/lane_health.json`
- `.ai/dropbox/state/docs_truth_receipt.json`
- `.ai/dropbox/state/story_promotion_receipt.json`
- `scripts/agents/status_swarm.sh`
- `scripts/agents/health_swarm.sh`
- `docs/policy/writer_story_promotion_rubric.md`

The repo also already treats `autoresearch` as advisory-only future research
doctrine rather than runtime authority.

The repo now also has a first repo-native watcher adapter seam:

- `.ai/swarm/watcher.yaml`
- `.ai/templates/watcher.md`
- `scripts/agents/codex_watch_adapter.py`
- `scripts/agents/start_watch_adapter.sh`
- `scripts/agents/status_watch_adapter.sh`
- `scripts/agents/audit_ai_surfaces.py`
- `.ai/dropbox/state/watcher_state.json`
- `.ai/dropbox/state/watcher_latest.json`
- `.ai/dropbox/state/watcher.lock`

That watcher is explicitly:

- advisory-only
- single-run locked
- `prd.json.activeStoryId` first
- bounded to JSON/QMD watcher packets plus archive copies under `data/`
- sandboxed for optional evals instead of writing back into main repo truth

The current shadow lane already provides the bounded ingredients that a watcher
should eventually supervise:

- point-in-time-safe walk-forward regime history
- bounded label families such as `tb_60m_atr1x` and `tb_240m_atr1x`
- `IsolationForest`
- `RandomForestClassifier`
- `XGBClassifier`
- settlement-owned spot-first backtest truth

## Gap

The repo still lacks the later-stage pieces that would let a Codex agent safely
watch the repo, suggest upgrades, and use ideas from
`https://github.com/karpathy/autoresearch` without creating governance drift.

Missing pieces:

- a proposal artifact schema for suggestions such as:
  - upgrades
  - subtraction recommendations
  - benchmark ideas
  - strategy-family experiments
- a machine-readable metrics registry that can judge whether a suggestion is
  actually better
- a repeated advisory runner contract that can:
  - backtest and replay over and over
  - walk forward over and over
  - score bounded challenger families repeatedly without needing a human to
    hand-curate each run
- a routing rule from watcher proposals into:
  - `docs/issues/`
  - `docs/gaps/`
  - `docs/plans/`
  - `docs/task/`
  - `prd.json`

## Why direct autoresearch is not drop-in

Karpathy's `autoresearch` is intentionally narrow:

- the human edits `program.md`
- the agent edits one file: `train.py`
- runs are compared on a fixed time budget
- improvement is judged by one scalar metric

Defi-engine is different:

- it is a multi-layer governed repo, not a single-file training harness
- it has multiple owner layers and promotion gates
- it needs writer-integrator to route findings into durable repo truth
- it cannot let an autonomous agent modify broad runtime surfaces directly

So the repo needs an adapter, not a direct drop-in.

## Why this helps `LABEL-001` and `STRAT-001`

This gap is not a side quest. It is a support seam for both:

- `LABEL-001`
  - the watcher can repeatedly score label and horizon definitions under
    backtest and walk-forward replay
- `STRAT-001`
  - the watcher can repeatedly compare bounded challenger families and emit
    strategy proposals or subtraction proposals

The watcher should stay advisory-only, but it should be able to generate
durable proposal artifacts fast enough that writer-integrator can keep
promoting the next bounded slices without human micromanagement.

## Close when

- proposal artifacts are standardized and writer-routable
- a metrics registry exists for accepting or rejecting suggested upgrades
- the repo has a bounded no-HITL advisory shadow loop for repeated backtest,
  walk-forward, and challenger scoring
- autoresearch-style agents are limited to advisory proposal generation until
  promotion rules explicitly widen their role
