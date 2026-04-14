# Paper Runtime Blockers

## Purpose

Track the durable blockers that still prevent the repo from being described as a runnable paper-trading engine.

This page is intentionally stricter than `docs/gaps/bootstrap_gap_register.md`. The gap register tracks general deferred capability; this file tracks the blockers that stop the post-ingest runtime descent from becoming real.

## Current Blocking Set

| Blocker | Why it blocks paper runtime | Current state | Close condition | Next action |
|------|-------|-------|-------|-------|
| Continuous capture ownership is not explicit | downstream layers cannot rely on freshness, completeness, or run cadence without a true runtime owner for ingest continuity | `capture/runner.py` is strong, but it is still described as bootstrap ingest rather than a continuous runtime authority | one repo-owned note or task defines cadence, source freshness expectations, failure states, and operator response rules | descend and execute `docs/task/continuous_capture_ownership.md` |
| `features/` is only partially runtime-ready | downstream layers now have deterministic feature lanes, but no policy-owned consumer turns them into explainable paper eligibility | `spot_chain_macro_v1`, `global_regime_inputs_15m_v1`, and freshness receipts exist behind `d5 materialize-features`, and `condition/` now consumes a bounded market-wide lane | one policy trace consumes feature-backed condition outputs without reaching back into providers or feature internals | descend from `docs/task/global_regime_condition_and_shadow_stack.md` into the first `policy/` trace task |
| `condition/` is only partially wired | the repo can now distinguish observed truth from regime interpretation, but the result still ends at a score instead of a governed paper decision | `global_regime_v1`, `condition_scoring_run`, and `condition_global_regime_snapshot_v1` exist, plus an advisory YAML bias stub | one policy-owned consumer records how condition state becomes eligibility or veto before any paper action is simulated | promote the advisory bias map into an explicit policy trace input |
| `policy/` and decision tracing are absent | there is no explicit strategy eligibility surface between regime logic and execution intent | placeholder package only | one decision-trace contract exists that records why a paper action is eligible or ineligible | define a policy trace schema before paper execution logic is added |
| `risk/` is not a real hard gate yet | paper actions would have no conservative final veto surface | placeholder package only | veto matrix, halt conditions, and fail-closed defaults are documented and implemented | define the first minimal paper-safe risk gate |
| `settlement/` has no paper session ledger | the repo has no truthful place to simulate fills, track paper positions, or report paper PnL | placeholder package only | paper session state, fill assumptions, and session receipts exist | define the first paper-session state model and close assumptions |
| `research_loop/` is only partially governed | the repo can now run bounded shadow experiments, but it still cannot compare them against realized paper outcomes | `intraday_meta_stack_v1`, `experiment_run`, `experiment_metric`, and QMD evidence artifacts exist behind `d5 run-shadow` | experiment comparison consumes realized paper-session receipts without promoting shadow models directly | keep the shadow lane bounded until `settlement/` owns paper outcome truth |

## Non-Blocking But Important

- provider-specific top-level CLI ergonomics are still optional
- Parquet export is still deferred
- Massive remains scaffold-only until entitlement and payload proof exist
- richer Helius protocol-aware decoding remains deferred

These matter, but they do not need to be solved before the first truthful paper-runtime descent is planned.

## Routing Rule

When a new task touches post-ingest runtime behavior, it should either:

- descend one blocker in this file, or
- update this file if the blocker list changed

That keeps runtime blockers durable instead of scattering them across handoff notes and one-off plans.
