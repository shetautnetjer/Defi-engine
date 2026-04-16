# Paper Runtime Blockers

## Purpose

Track the durable blockers that still prevent the repo from being described as a runnable paper-trading engine.

This page is intentionally stricter than `docs/gaps/bootstrap_gap_register.md`. The gap register tracks general deferred capability; this file tracks the blockers that stop the post-ingest runtime descent from becoming real.

## Current Blocking Set

| Blocker | Why it blocks paper runtime | Current state | Close condition | Next action |
|------|-------|-------|-------|-------|
| Continuous capture ownership is not explicit | downstream layers cannot rely on freshness, completeness, or run cadence without a true runtime owner for ingest continuity | `capture/runner.py` is strong, but it is still described as bootstrap ingest rather than a continuous runtime authority | one repo-owned note or task defines cadence, source freshness expectations, failure states, and operator response rules | descend and execute `docs/task/continuous_capture_ownership.md` |
| Execution intent between `risk/` and `settlement/` is still manual-explicit | the repo now has a paper ledger, but `PaperSettlement` still requires explicit `risk_verdict_id` plus `quote_snapshot_id`, so a market-wide `allowed` risk verdict does not yet become runtime-owned trade intent on its own | `risk_global_regime_gate_v1` exists and `PaperSettlement` exists, but the selector for mint / size / entry-exit intent is not owned | a repo-owned contract persists or selects explicit quote-backed execution intent without inventing hidden strategy authority | define the first bounded execution-intent owner downstream of risk and upstream of settlement |
| `research_loop/` is only partially governed | the repo can now run bounded shadow experiments, explicit policy traces, explicit risk verdicts, and explicit paper settlement receipts, but it still cannot compare research outputs against realized paper outcomes | `intraday_meta_stack_v1`, `experiment_run`, `experiment_metric`, `paper_session`, `paper_fill`, `paper_position`, and `paper_session_report` now exist, but the comparison path is still missing | experiment comparison consumes realized paper-session receipts without promoting shadow models directly | descend the realized-feedback comparison path now that settlement truth exists |

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
