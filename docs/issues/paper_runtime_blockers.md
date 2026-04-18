# Paper Runtime Blockers

## Purpose

Track the durable blockers that still prevent the repo from being described as a runnable paper-trading engine.

This page is intentionally stricter than `docs/gaps/bootstrap_gap_register.md`. The gap register tracks general deferred capability; this file tracks the blockers that stop the post-ingest runtime descent from becoming real.

## Current Blocking Set

No current Stage 1 runtime-owner blocker remains open.

The repo now has:

- explicit policy traces
- explicit risk vetoes
- explicit execution intent
- explicit quote-backed paper settlement

Future work is still required, but it is now Stage 2+ truth work rather than a
missing Stage 1 runtime owner.

The accepted Stage 2 backtest truth slice is also no longer open:

- `BACKTEST-001` landed a settlement-owned spot-first replay ledger through
  `BacktestTruthOwner` plus `backtest_session_v1`, `backtest_fill_v1`,
  `backtest_position_v1`, and `backtest_session_report_v1`
- the next governed product gaps are now canonical label truth and strategy
  registry/challenger governance rather than another paper-runtime seam

## Recently Cleared

- `EXEC-001` is now accepted repo truth:
  - `execution_intent/owner.py` owns the bounded paper-only `execution_intent_v1`
    surface between `risk/` and `settlement/`.
  - The owner persists or rejects explicit quote-backed spot-only mint, size,
    and entry intent and fails closed on ambiguous, unsupported, or stale
    inputs.
  - `PaperSettlement` now consumes `execution_intent_id` instead of inferring
    hidden strategy selection from `risk_verdict_id` plus `quote_snapshot_id`
    alone.
  - Runtime authority remains bounded: intent is paper-only, spot-first, and
    does not imply live execution, promotion, or derivatives support.
- `RESEARCH-001` is now accepted repo truth:
  - `research_loop/realized_feedback.py` replays experiment config, reads settlement-owned paper truth, and persists advisory comparison receipts in `experiment_realized_feedback_v1`.
  - `ShadowRunner` now invokes the comparator after run-level experiment metrics land, keeping settlement read-only and leaving policy/risk/runtime authority unchanged.
  - The comparison stays bounded to mint + regime-bucket + backward-ASOF matching and the latest available session snapshot instead of claiming full exit-lifecycle governance.
- `SOURCE-001` is now accepted repo truth:
  - `capture/lane_status.py` owns the governed capture-lane manifest and freshness doctrine.
  - `FeatureMaterializer` consumes that shared source-owner snapshot instead of a private freshness copy.
  - `d5 status` now exposes per-lane freshness states, eligibility, and blockers directly.
- `capture_cursor` remains explicitly deferred in v1 and is not treated as runtime-authoritative completeness yet.

## Non-Blocking But Important

- provider-specific top-level CLI ergonomics are still optional
- Parquet export is still deferred
- Massive still needs broader entitlement proof and coverage before it can be treated as a fully mature market-data source
- richer Helius protocol-aware decoding remains deferred

These matter, but they do not need to be solved before the first truthful paper-runtime descent is planned.

## Routing Rule

When a new task touches post-ingest runtime behavior, it should either:

- descend one blocker in this file
- update this file if the blocker list changed

That keeps runtime blockers durable instead of scattering them across handoff notes and one-off plans.
