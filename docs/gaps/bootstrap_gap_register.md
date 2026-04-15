# Bootstrap Gap Register

This file tracks deferred or missing capabilities that should not be mistaken for shipped behavior.

## Public Surface Gaps

- `doctor` command is missing.
  - Current state: CLI exposes `init`, `capture`, `materialize-features`, `score-conditions`, `run-shadow`, `status`, and `sync-duckdb`.
  - Close when config, filesystem, source-lane, feature-lane, and condition-lane health checks are implemented as a dedicated operator command.

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

- `features/` is only partially implemented.
  - Current state: `spot_chain_macro_v1` and `global_regime_inputs_15m_v1` exist, but a broader feature catalog, feature serving, and stronger operator-level feature governance are still missing.

- `condition/` is only partially implemented.
  - Current state: `global_regime_v1` exists as one bounded regime scorer with latest-snapshot persistence, but broader condition coverage and policy consumption are still missing.

- `research_loop/` is only partially implemented.
  - Current state: `intraday_meta_stack_v1` exists as one bounded, point-in-time-safe shadow lane, but it remains research-only and does not compare against paper-session outcomes yet.

- `policy/`, `risk/`, `settlement/`, `models/`, and `trajectory/` are mostly placeholders.
  - Current state: package boundaries exist, but they do not yet implement policy eligibility, hard vetoes, paper fills, governed model promotion, or promoted forecast ownership.

## Validation Gaps

- Live provider integration is not part of the default test pass.
  - Current state: the repo has live-gated Jupiter and Helius integration harnesses, but default `pytest` remains offline-safe and CI does not execute live provider tests.
  - Close when the repo decides how live tests should be invoked and recorded.

- Coinbase live integration is not yet covered by a gated operator receipt.
  - Current state: Helius and Jupiter have live-gated integration harnesses, but Coinbase market-data capture is still only covered by offline-safe tests and manual smoke receipts.

- Shadow-model evidence remains non-promoting.
  - Current state: point-in-time safety for the current regime/shadow lane is repaired, but policy, risk, settlement, and governed promotion still do not consume those outputs.

## Documentation Gaps

- `docs/runbooks/feature_condition_shadow_cycle.md` is the first current downstream operator runbook, but broader day-two incident playbooks are still missing.
  - Close when the repo has dedicated recovery or incident runbooks for stale lanes, experiment drift, and paper-session operations.

- `docs/math/regime_shadow_modeling_contracts.md` now documents the current bounded modeling contract, but the repo still lacks a broader math catalog for future policy, risk, settlement, and trajectory work.

- `docs/setup/solana_tooling_wsl.md` is deferred.
  - Close when local Solana CLI or Anchor setup becomes part of an active implementation slice instead of background context.
