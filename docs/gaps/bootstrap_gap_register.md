# Bootstrap Gap Register

This file tracks deferred or missing capabilities that should not be mistaken for shipped behavior.

## Public Surface Gaps

- `doctor` command is missing.
  - Current state: CLI exposes `init`, `capture`, `status`, and `sync-duckdb`.
  - Close when config, filesystem, and provider-health checks are implemented as a dedicated operator command.

- Provider-specific top-level capture commands are missing.
  - Current state: all capture flows route through `d5 capture <provider>`.
  - Close when CLI ergonomics are intentionally widened and documented.

## Storage And Ingest Gaps

- Parquet export is not implemented.
  - Current state: `data/parquet/` directories are provisioned, but `RawStore` only writes JSONL.

- Helius normalization remains bounded.
  - Current state: tracked-address discovery and `solana_transfer_event` exist, but richer instruction decoding and protocol-aware event modeling are still deferred.

- Helius websocket capture is still raw-first and non-resumable.
  - Current state: websocket capture now has bounded reconnect, heartbeat, and notification-count semantics, but it still does not implement durable resumability or canonical websocket projections.

- Coinbase is market-data only.
  - Current state: products, candles, trades, and L2 book snapshots are captured, but execution, paper fills, and slippage modeling are not implemented.

- Massive ingestion is scaffold-only.
  - Current state: the client intentionally fails closed and the CLI surfaces auth and entitlement failures explicitly until endpoint proof and payload examples are confirmed.

## Engine Layer Gaps

- `condition/`, `features/`, `policy/`, `risk/`, `settlement/`, `models/`, `research_loop/`, and `trajectory/` are mostly placeholders.
  - Current state: package boundaries exist, but they do not implement market logic, risk gates, paper fills, model orchestration, or research automation.

## Validation Gaps

- Live provider integration is not part of the default test pass.
  - Current state: the repo has a live-gated Jupiter integration harness, but default `pytest` remains offline-safe and CI does not execute live provider tests.
  - Close when the repo decides how live tests should be invoked and recorded.

- Coinbase live integration is not yet covered by a gated operator receipt.
  - Current state: Helius and Jupiter now have live-gated integration harnesses, but Coinbase market-data capture is still only covered by offline-safe tests and manual smoke receipts.

## Documentation Gaps

- `docs/math/math_grounding.md` is deferred.
  - Close when the repo has real feature/materialization and model behavior that needs normative math guidance.

- `docs/setup/solana_tooling_wsl.md` is deferred.
  - Close when local Solana CLI or Anchor setup becomes part of an active implementation slice instead of background context.
