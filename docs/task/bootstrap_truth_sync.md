# Bootstrap Truth Sync

Completed bootstrap closeout slice.

This file remains as a historical task surface for the Alembic-authority and first-test-surface pass that landed on 2026-04-12.

## What Landed

- Python distribution metadata was aligned to `d5engine`
- the import path remained `d5_trading_engine`
- the operator CLI remained `d5`
- `d5 init` became Alembic-driven
- the direct ORM bootstrap helper was renamed to `create_all_for_tests_only()`
- the first pytest surface landed for config, migrations/bootstrap, CLI smoke, mocked adapters, and docs truth contracts
- bootstrap docs were synchronized around Alembic as the operator bootstrap authority

## Historical Exit Criteria

- `d5 init` applies Alembic migrations to head
- direct ORM bootstrap is clearly marked dev/test-only
- `tests/` exists and covers the bootstrap validation seam
- README and runbooks describe Alembic as the operator bootstrap authority
- implemented, scaffolded, and missing areas are recorded in `docs/project/bootstrap_inventory.md`
- deferred work is captured in `docs/gaps/bootstrap_gap_register.md`

## Superseded By

- active task surface: `docs/task/ingest_hardening_phase_1.md`
- historical receipt: `docs/handoff/2026-04-12_bootstrap_phase_1.md`
