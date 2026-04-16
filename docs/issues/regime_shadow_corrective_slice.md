# Regime And Shadow Corrective Slice

## Purpose

Track the concrete corrective work that was required before `global_regime_v1` and `intraday_meta_stack_v1` could be treated as trustworthy paper-runtime support surfaces.

This page is narrower than `paper_runtime_blockers.md`. The findings below are now materially implemented in repo truth and should be treated as a historical corrective receipt plus guardrail, not as a hard blocker that prevents the first policy consumer from existing.

## Findings

| Finding | Why it matters | Current state | Close condition | Next action |
|------|-------|-------|-------|-------|
| Shadow evaluation used future-informed regime fits | shadow metrics are optimistic if regime labels are generated from a model trained on future rows | the initial shadow lane merged regime history built from one latest-window fit | shadow features are generated from a walk-forward regime history with past-only fits and explicit refit metadata | keep `intraday_meta_stack_v1` advisory-only until the walk-forward repair and validation land |
| Same-day FRED forward-fill could look ahead | intraday feature rows can consume macro values before the observation was actually captured | feature materialization only checked `observation_date <= bucket_date` | feature rows only consume FRED observations whose `captured_at <= bucket_end_utc`, while still falling back to earlier captured values | enforce captured-at timing in both feature lanes and add timing tests |
| `d5 status` hid the latest failed condition run | operators could see a stale successful snapshot even when the newest condition run failed | the status surface filtered to `ConditionScoringRun.status=success` before rendering | `d5 status` shows the newest run regardless of status and does not fall back to older success receipts | surface failed-run metadata and test the failure path explicitly |

## Guardrail

These findings are now materially closed and revalidated in targeted tests. The remaining guardrail is narrower:

- `global_regime_v1` is now a valid input to the first explicit `policy/` trace owner
- `intraday_meta_stack_v1` remains a shadow-only research surface
- policy, risk, and settlement work should not promote the current shadow metrics into runtime authority

## Verification Target

The corrective slice is materially complete because:

1. the scorer provides a walk-forward regime history for shadow use
2. shadow metrics are built from chronologically ordered, point-in-time-safe features
3. same-day macro availability is enforced by `captured_at`
4. `d5 status` reports the latest failed condition run without falling back
5. targeted tests cover the point-in-time, macro-timing, and status-failure paths
