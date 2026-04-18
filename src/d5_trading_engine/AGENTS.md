# `src/d5_trading_engine` Navigation

This package is the runtime and research implementation surface for
Defi-engine.

Use this file as the quick package map:

- `adapters/`
  - provider access only
- `normalize/`
  - provider-specific normalization into canonical shapes
- `capture/`
  - capture orchestration and lane status
- `features/`
  - deterministic feature and label materialization
- `condition/`
  - regime and condition scoring
- `policy/`
  - strategy eligibility and traceability
- `risk/`
  - hard vetoes and conservative controls
- `execution_intent/`
  - governed paper execution intent only
- `settlement/`
  - paper fills, positions, and report ownership
- `paper_runtime/`
  - paper-session orchestration
- `reporting/`
  - QMD and artifact writing
- `research_loop/`
  - advisory experiments, proposals, reviews, and comparisons
- `storage/`
  - canonical SQL truth, raw stores, and analytics mirror boundaries
- `models/`
  - runtime-adjacent and shadow-only model helpers
- `trajectory/`
  - advisory forecasting and scenario generation only

`cli.py` is the main repo entrypoint. Keep it thin: dispatch to the owning
module instead of moving owner logic into the CLI.

If a change crosses multiple owners, stop and check whether the slice is really
an integration change or whether one layer is taking work that belongs
elsewhere.
