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
- bounded shadow evaluation:
  - `intraday_meta_stack_v1`

Still missing as runtime owners:

- `policy/`
- `risk/`
- `settlement/`

## Authority order

1. code/config/schema truth in this repo
2. explicit policy snapshots when they exist
3. strategy eligibility and parameter surfaces
4. risk gate
5. paper settlement and feedback

Forecasting, shadow evaluation, memory, and external research are advisory only.

## Shared rules

- Work one accepted story at a time.
- Read the current repo map before proposing anything.
- Do not invent a new surface if an existing one already serves the need.
- Do not silently widen runtime authority.
- Default safe action is no-trade and no-promotion.
- `policy/`, `risk/`, and `settlement/` are the next missing owners unless a
  real blocker in `source/`, `features/`, or `condition/` prevents progress.

## Write boundaries

- research lane writes only to `.ai/dropbox/research/`
- builder lane writes code/tests and `.ai/dropbox/build/`
- architecture lane writes only to `.ai/dropbox/architecture/` unless the
  writer-integrator explicitly accepts a doc patch for the current story
- writer-integrator owns:
  - `.ai/dropbox/state/`
  - `prd.json`
  - `progress.txt`
  - accepted docs synchronization

## Skill routing

- research lane:
  - `research-skill`
  - `exa-search-skill`
  - `crawl4ai-skill`
- builder lane:
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
