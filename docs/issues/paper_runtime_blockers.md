# Paper Runtime Blockers

## Purpose

Track the durable blockers that still prevent the repo from being described as a runnable paper-trading engine.

This page is intentionally stricter than `docs/gaps/bootstrap_gap_register.md`. The gap register tracks general deferred capability; this file tracks the blockers that stop the post-ingest runtime descent from becoming real.

## Current Blocking Set

| Blocker | Why it blocks paper runtime | Current state | Close condition | Next action |
|------|-------|-------|-------|-------|
| Execution intent between `risk/` and `settlement/` is still manual-explicit | the repo now has a paper ledger, but `PaperSettlement` still requires explicit `risk_verdict_id` plus `quote_snapshot_id`, so a market-wide `allowed` risk verdict does not yet become runtime-owned trade intent on its own | `risk_global_regime_gate_v1` exists and `PaperSettlement` exists, but the selector for mint / size / entry-exit intent is not owned | a repo-owned contract persists or selects explicit quote-backed spot-only mint, size, and entry-exit intent downstream of risk and upstream of settlement | descend into `EXEC-001` once higher-priority follow-ons are clear |

## Recently Cleared

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
- Massive remains scaffold-only until entitlement and payload proof exist
- richer Helius protocol-aware decoding remains deferred

These matter, but they do not need to be solved before the first truthful paper-runtime descent is planned.

## Routing Rule

When a new task touches post-ingest runtime behavior, it should either:

- descend one blocker in this file
- update this file if the blocker list changed

That keeps runtime blockers durable instead of scattering them across handoff notes and one-off plans.
