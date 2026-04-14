# Paper Runtime Blockers

## Purpose

Track the durable blockers that still prevent the repo from being described as a runnable paper-trading engine.

This page is intentionally stricter than `docs/gaps/bootstrap_gap_register.md`. The gap register tracks general deferred capability; this file tracks the blockers that stop the post-ingest runtime descent from becoming real.

## Current Blocking Set

| Blocker | Why it blocks paper runtime | Current state | Close condition | Next action |
|------|-------|-------|-------|-------|
| Continuous capture ownership is not explicit | downstream layers cannot rely on freshness, completeness, or run cadence without a true runtime owner for ingest continuity | `capture/runner.py` is strong, but it is still described as bootstrap ingest rather than a continuous runtime authority | one repo-owned note or task defines cadence, source freshness expectations, failure states, and operator response rules | promote a bounded continuous-capture ownership task from the bridge note |
| `features/` has no real materialization contract | no downstream layer can consume stable derived truth without coupling directly to ingest or canonical raw-ish tables | placeholder package and research scaffolding tables exist, but no actual feature registry or materialization flow exists | first feature registry, materialization run contract, and canonical inputs are documented and implemented | define the first feature set for spot, chain, and macro inputs |
| `condition/` has no real scorer contract | the repo cannot distinguish observed truth from regime interpretation yet | placeholder package only | one bounded scorer path exists with explicit inputs, outputs, and receipts | write a condition scorer design note after the first feature contract lands |
| `policy/` and decision tracing are absent | there is no explicit strategy eligibility surface between regime logic and execution intent | placeholder package only | one decision-trace contract exists that records why a paper action is eligible or ineligible | define a policy trace schema before paper execution logic is added |
| `risk/` is not a real hard gate yet | paper actions would have no conservative final veto surface | placeholder package only | veto matrix, halt conditions, and fail-closed defaults are documented and implemented | define the first minimal paper-safe risk gate |
| `settlement/` has no paper session ledger | the repo has no truthful place to simulate fills, track paper positions, or report paper PnL | placeholder package only | paper session state, fill assumptions, and session receipts exist | define the first paper-session state model and close assumptions |
| `research_loop/` is not governed | no bounded path exists for comparing realized paper outcomes against shadow alternatives | placeholder package only | experiment comparison and proposal workflow are explicit and non-promoting | keep deferred until paper-session receipts stabilize |

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
