# Ingest Hardening Phase 1

Active execution surface for turning bootstrap capture into a trustworthy multi-source ingest foundation.

## Goal

Initialize the canonical truth DB cleanly, establish one real provider-backed integration path through Jupiter, and make Helius and Massive operator behavior truthful so later source graduation work starts from explicit contracts instead of scaffold drift.

## This Slice Covers

- using `d5 init` as the first operational step for creating the canonical SQLite truth DB
- creating the DuckDB mirror only after a successful sync from SQLite
- adding a live-gated Jupiter integration harness for tokens + prices
- adding a simple comma-separated `HELIUS_TRACKED_ADDRESSES` config surface
- making `d5 capture helius-transactions` fail explicitly when tracked addresses are missing
- making `d5 capture massive-crypto` fail closed with a real operator-visible error on auth, entitlement, or placeholder-endpoint failures
- keeping the public CLI shape unchanged: `init`, `capture`, `status`, `sync-duckdb`
- updating docs, validation notes, and CI so the active repo surface matches the code again

## Exit Criteria

- `d5 init` creates `data/db/d5.db` through Alembic migrations
- `d5 sync-duckdb ...` can create `data/db/d5_analytics.duckdb` from the SQLite truth DB
- default `pytest tests -q` stays offline-safe and secretless
- a live-gated Jupiter integration test exists for tokens + prices and validates raw files, raw SQL rows, canonical rows, health events, and DuckDB sync
- Helius capture no longer silently succeeds when no tracked addresses are configured
- Massive capture no longer reports success when it failed closed
- docs inventory, task, gap, architecture, README, and validation surfaces describe the new ingest-hardening truth
- offline CI exists for compile/import, unit tests, and targeted Ruff

## Deferred On Purpose

- `doctor`
- provider-specific top-level CLI commands
- Parquet export
- deep Helius canonical projections
- Helius websocket hardening beyond explicit scaffold status
- deeper Massive entitlement expansion beyond first-pass REST reference and historical minute aggregates
- live-provider integration in default CI

## Next Actions After This Slice

1. Graduate Helius REST capture from readiness-only into the first real canonical projection.
2. Prove one real Massive endpoint and entitlement shape before widening its implementation surface.
3. Decide when to add `doctor` and whether generic `capture` stays the long-term CLI shape.
