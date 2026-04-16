# Common Lane Doctrine

## Mission

Use this swarm to move Defi-engine toward a governed paper engine without
inventing authority that the repo does not yet own.

## Current truthful repo state

Implemented and real now:

- canonical source truth in SQLite
- bounded deterministic features:
  - `spot_chain_macro_v1`
  - `global_regime_inputs_15m_v1`
- bounded condition scoring:
  - `global_regime_v1`
- explicit policy tracing:
  - `global_regime_v1`
  - `policy_global_regime_trace_v1`
- explicit risk gating:
  - `RiskGate`
  - `risk_global_regime_gate_v1`
- explicit paper settlement:
  - `PaperSettlement`
  - `paper_session`
  - `paper_fill`
  - `paper_position`
  - `paper_session_report`
- bounded shadow evaluation:
  - `intraday_meta_stack_v1`

Remaining blockers to a fully governed paper engine:

- continuous capture ownership still needs an explicit runtime owner
- runtime-owned execution intent between `risk/` and `settlement/` does not exist yet
- `research_loop/` still does not compare realized paper outcomes against shadow receipts
- the swarm still needs a clean terminal completion contract that distinguishes
  backlog exhaustion, audit-known follow-ons, and true terminal completion

## Authority order

1. code/config/schema truth in this repo
2. explicit policy snapshots when they exist
3. strategy eligibility and parameter surfaces
4. risk gate
5. paper settlement and feedback

Forecasting, shadow evaluation, memory, and external research are advisory only.

## Shared rules

- Work one accepted story at a time.
- Keep looping until no eligible stories remain and the final architect +
  writer-integrator audit is clean.
- Keep the existing 4-lane swarm. Do not invent new permanent lanes.
- Finder work runs inside trusted lanes:
  - `architecture-finder` is subtraction-first
  - `research-finder` is evidence-first
- Finder outputs are advisory only until writer-integrator promotes, defers,
  rejects, or marks them audit-known.
- Read the current repo map before proposing anything.
- Do not invent a new surface if an existing one already serves the need.
- Do not silently widen runtime authority.
- Default safe action is no-trade and no-promotion.
- Future stories should now descend the real blocker list instead of assuming a
  placeholder owner is still missing.

## Write boundaries

- research lane writes only to `.ai/dropbox/research/`
- builder lane writes code/tests and `.ai/dropbox/build/`
- architecture lane writes only to `.ai/dropbox/architecture/` unless the
  writer-integrator explicitly accepts a doc patch for the current story
- writer-integrator owns:
  - `.ai/dropbox/state/`
  - `accepted_receipts/*.json`
  - `prd.json`
  - `progress.txt`
  - accepted docs synchronization

## Skill routing

- research lane:
  - `research-skill`
  - `exa-search-skill`
  - `crawl4ai-skill`
- builder lane:
  - default model: ChatGPT 5.4
  - `jetbrains-mcp`
  - repo-native tests/checks
- architecture lane:
  - `jetbrains-skill`
  - `jetbrains-mcp`
- writer-integrator lane:
  - repo docs
  - `ralph`
  - `ralph-loop`
  - current repo map

## Outputs

Every lane should leave:

- what changed or what was learned
- files touched or artifacts written
- checks run
- residual risks or open questions
