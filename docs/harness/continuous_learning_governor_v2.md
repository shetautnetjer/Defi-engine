# Continuous Learning Governor V2

## Purpose

Define the future stage where D5 evolves through candidate overlays while runtime remains protected by promotion gates.

## Current Stage

Current repo law remains paper-first. The learning governor is not live authority.

## Candidate Overlays

Mutable surfaces must be versioned overlays, not random edits.

Allowed overlay families:

- `candidate_label_program_overlay_v1`
- `candidate_feature_toggle_overlay_v1`
- `candidate_condition_overlay_v1`
- `candidate_policy_overlay_v1`
- `candidate_risk_overlay_v1`
- `candidate_source_transform_overlay_v1`

## Overlay States

- `draft`
- `research`
- `shadow`
- `paper_candidate`
- `paper_approved`
- `micro_live_candidate`
- `micro_live_approved`
- `rejected`
- `rolled_back`

## Promotion Ladder

```text
research
→ shadow
→ paper
→ micro_live
→ scaled_live
```

## Paper Promotion Gate

A candidate may enter paper runtime only if:

- baseline comparison passes
- multiple windows pass
- no material drawdown deterioration
- cost/slippage assumptions are documented
- QMD packet exists
- SQL evidence is complete
- rollback target exists

## Micro-Live Gate

Micro-live remains future-only and requires explicit operator scope.

Minimum gate:

- rolling paper win rate ≥ 80%
- minimum trade count ≥ 20
- average ≥ 1 filled trade/week
- net expectancy > 0 after fees/slippage
- profit factor > 1.5
- max drawdown under allowed bound
- no unresolved feed/quote/settlement incidents
- decisions reconstructable from SQL/QMD
- prior approved baseline identified
- rollback target identified
- hard kill switch exists

## Runtime Separation

Runtime cannot rewrite itself mid-cycle.

Correct loop:

```text
runtime
→ evidence
→ research candidate overlays
→ comparison
→ promotion decision
→ new approved runtime version
→ runtime
```

Incorrect loop:

```text
runtime
→ self-edits immediately
→ runtime
```

## Daily Cadence

- collect new source data
- refresh feature windows
- rescore conditions
- settle paper sessions
- write evidence rollup
- generate candidate batch if needed

## Weekly Cadence

- rerun walk-forward comparisons
- refresh profile evidence
- retire stale candidates
- evaluate promotion candidates
- update baselines
