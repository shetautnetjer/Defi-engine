# Bootstrap Inventory

Current snapshot of `Defi-engine` after the source-expansion pre-conditions slice on 2026-04-12.

## Public Surface

- Python distribution metadata: `d5engine`
- Import path: `d5_trading_engine`
- Operator CLI: `d5`
- Runtime data paths:
  - SQLite truth DB: `data/db/d5.db`
  - DuckDB mirror: `data/db/d5_analytics.duckdb`
  - Coinbase raw DB: `data/db/coinbase_raw.db`
  - Raw landing zone: `data/raw/{provider}/{YYYY-MM-DD}/`

## Inventory

| Area | State | Notes |
|------|-------|-------|
| Project metadata | implemented | `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `alembic.ini` are present |
| Config/common | implemented | settings now include the mint-locked universe, Jupiter throttle, Coinbase raw DB path, and UTC event-time helpers |
| SQLite truth layer | implemented | SQLAlchemy engine + ORM models + Alembic migrations exist |
| DB bootstrap path | implemented | `d5 init` runs Alembic migrations to head |
| Raw storage | partial | JSONL writing is implemented; Parquet directories exist but Parquet export is not written yet |
| DuckDB mirror | implemented | SQLite attach/copy flow exists in `storage/analytics/duckdb_mirror.py` |
| Jupiter adapter/normalizer | implemented | spot token list, prices, and two-sided quotes with capture metadata are present |
| Helius adapter | partial | enhanced transaction REST, tracked-address discovery, and bounded websocket raw capture exist |
| Helius normalizer | partial | address/program registry population and `solana_transfer_event` exist; deeper program decoding is still deferred |
| Coinbase adapter/normalizer | partial | public products, candles, trade prints, and L2 book capture exist; execution and fill modeling are deferred |
| Massive adapter/normalizer | scaffolded | fail-closed readiness/probe path surfaces auth and entitlement failure explicitly |
| Capture runner | implemented | ingest run bookkeeping, raw write, normalization, and health logging are wired across Jupiter, Helius, Coinbase, FRED, and Massive |
| CLI | implemented | current commands are `init`, `capture`, `status`, and `sync-duckdb` |
| Condition/risk/settlement | scaffolded | placeholder modules exist, but engine behavior is not implemented |
| Features/models/policy/research_loop/trajectory | scaffolded | package surfaces exist with little or no runtime logic |
| Tests | implemented | default `pytest` stays offline-safe; a live-gated Jupiter integration harness exists for tokens + prices |
| Docs | partial | docs inventory, architecture, runbook, validation notes, active task docs, and new planning docs exist |

## Current Drifts From The Earlier Bootstrap Sketch

- the current CLI is generic (`d5 capture <provider>`) rather than provider-specific top-level commands
- the CLI lives in `src/d5_trading_engine/cli.py`, not `src/d5_trading_engine/cli/main.py`
- the current scaffold uses single-file placeholders like `condition/scorer.py`, `risk/gate.py`, and `settlement/paper.py`
- README and docs must continue to treat current code as truth until deeper research and runtime layers are actually implemented
