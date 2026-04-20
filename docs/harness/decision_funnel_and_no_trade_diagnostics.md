# Decision Funnel and No-Trade Diagnostics

## Purpose

The engine must explain not only trades, but also non-trades.

If a 300-day training window produces zero trades, the system must identify the failure surface.

## Funnel

```text
training window coverage
→ SQL coverage
→ feature coverage
→ condition coverage
→ strategy candidate generation
→ policy eligibility
→ risk approval
→ quote/fill availability
→ paper settlement
```

## Core Diagnostic Tables

### `research.training_window_manifest_v1`

Captures whether the expected historical window exists in raw files, Parquet, and SQL.

### `research.feature_window_manifest_v1`

Captures whether the expected bars became valid feature rows.

### `runtime.decision_cycle_v1`

One row per decision cycle.

### `runtime.opportunity_event_v1`

One row per strategy opportunity or no-opportunity event.

### `runtime.decision_gate_trace_v1`

One row per gate verdict.

### `research.no_trade_diagnostic_v1`

Rollup of no-trade reasons for a run/window.

## Required CLI

```bash
d5 diagnose training-window --regimen quickstart_300d --json
d5 diagnose gate-funnel --run latest --json
d5 diagnose no-trades --run latest --window 300d --json
```

## Required Output

Example zero-trade diagnosis:

```json
{
  "window_days": 300,
  "total_decision_cycles": 28800,
  "valid_feature_cycles": 27600,
  "valid_condition_cycles": 27400,
  "strategy_candidates": 0,
  "policy_allowed": 0,
  "risk_approved": 0,
  "paper_filled": 0,
  "primary_failure_surface": "strategy_candidate_generation_failure",
  "top_reason_codes": [
    ["no_strategy_signal", 28800]
  ],
  "recommended_next_action": "Run always-candidate sanity baseline and threshold sensitivity sweep."
}
```

## Failure Surfaces

Allowed primary failure surfaces:

- `data_coverage_gap`
- `feature_materialization_gap`
- `condition_churn_or_staleness`
- `strategy_candidate_generation_failure`
- `policy_overblocking`
- `risk_overblocking`
- `quote_fill_unavailability`
- `settlement_feedback_gap`
- `unknown`

## Design Rule

No-trade is not a blank outcome. It is a decision state with evidence.
