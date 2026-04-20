# Evidence-to-Experiment Loop V1.1

## Purpose

Create a learning layer that turns existing SQL/QMD/JSON artifacts into normalized evidence, then into small comparable experiment batches.

## Problem

The repo can produce many artifacts without learning. A proposal is not learning until it is compared, tested, and linked to outcomes.

## Loop

```text
artifact scan
→ evidence units
→ evidence rollup
→ failure-family ranking
→ experiment batch
→ baseline comparison
→ keep/reject/shadow
```

## Evidence Levels

### Level 1 — Evidence Unit

One normalized row per artifact, run, receipt, proposal, review, comparison, or paper session.

### Level 2 — Evidence Rollup

One summary of evidence maturity, failure-family distribution, trading-loop health, and coverage.

### Level 3 — Experiment Batch

A small batch of comparable candidate experiments selected from the failure-family registry.

## Evidence Maturity Stages

Allowed stages:

- `proposed`
- `reviewed`
- `compared`
- `backtested`
- `walk_forward_tested`
- `paper_tested`
- `superseded`
- `rejected`

## Failure-Family Ranking

The rollup must rank multiple possible explanations, not pick one forever.

Example:

```json
{
  "top_failure_families": [
    {"family": "strategy_candidate_generation_failure", "score": 0.86},
    {"family": "risk_overblocking", "score": 0.62},
    {"family": "quote_fill_unavailability", "score": 0.41}
  ]
}
```

## Batch Requirements

Every selected batch must include:

1. mainline candidate
2. isolate-the-cause candidate
3. falsification/sanity candidate

## Non-Authority Rule

This loop may propose. It may not promote runtime behavior by itself.

## Initial CLI Targets

```bash
d5 training evidence-rollup --json
d5 training evidence-gap --json
d5 training experiment-batch --json
d5 training review-batch --batch latest --json
d5 compare-proposals --proposal-kind candidate_overlay_experiment --choose-top --json
d5 training run-experiment-batch --batch latest --json
d5 training rehearsal --json
```

## Acceptance Criteria

- evidence units are schema-valid
- rollup includes maturity counts
- rollup includes no-trade funnel counts when available
- selected failure family has alternatives listed
- batch includes a falsification candidate
- all outputs have SQL/QMD/JSON references
- rehearsal proves candidate-to-paper-profile evolution in scratch
- rehearsal exports CSV and Parquet ledger when parquet support is available
