# Feature, Condition, And Shadow Cycle Runbook

Operator path for the current downstream loop after source capture is already working.

## Purpose

Run the bounded downstream stack in the intended order:

1. verify source freshness
2. materialize deterministic features
3. score the bounded global regime
4. run the bounded shadow-only ensemble
5. inspect receipts and artifacts without widening runtime authority

## Prerequisites

- Python 3.12+
- a virtualenv or other isolated Python environment
- `.env` created from `.env.example`
- provider keys filled in for the captures you plan to run
- canonical truth already seeded with the relevant source captures

At minimum, the downstream loop depends on recent receipts for:

- `jupiter-prices`
- `jupiter-quotes`
- `coinbase-products`
- `coinbase-candles`
- `coinbase-market-trades`
- `coinbase-book`
- `fred-observations`

The minute feature lane can also consume bounded Helius transfer context when it exists.

## Setup

```bash
cd /home/netjer/Projects/AI-Frame/Brain/Defi-engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Step 1. Initialize And Check Source Freshness

```bash
d5 init
d5 status
```

Expected outcome:

- `d5 init` applies Alembic migrations to the canonical SQLite truth database
- `d5 status` shows recent ingest runs and the latest provider health events
- if a condition run has failed recently, `d5 status` shows that failure instead of hiding it behind an older success

If source freshness looks weak, refresh the relevant lanes before moving downstream:

```bash
d5 capture jupiter-prices
d5 capture jupiter-quotes
d5 capture coinbase-products
d5 capture coinbase-candles
d5 capture coinbase-market-trades
d5 capture coinbase-book
d5 capture fred-observations
```

## Step 2. Materialize Deterministic Features

Run the minute execution-context lane first:

```bash
d5 materialize-features spot-chain-macro-v1
```

Then run the market-wide 15-minute regime lane:

```bash
d5 materialize-features global-regime-inputs-15m-v1
```

Expected outcome:

- each command prints a success line with a `feature_materialization_run.run_id`
- `spot_chain_macro_v1` writes rows into `feature_spot_chain_macro_minute_v1`
- `global_regime_inputs_15m_v1` writes rows into `feature_global_regime_input_15m_v1`
- `feature_materialization_run` records freshness snapshots and input windows

Quick verification:

```bash
sqlite3 data/db/d5.db "SELECT run_id, feature_set, status, row_count FROM feature_materialization_run ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/db/d5.db "SELECT count(*) FROM feature_spot_chain_macro_minute_v1;"
sqlite3 data/db/d5.db "SELECT count(*) FROM feature_global_regime_input_15m_v1;"
```

## Step 3. Score The Bounded Regime Condition

```bash
d5 score-conditions global-regime-v1
```

Expected outcome:

- the command prints a success line with:
  - `condition_scoring_run.run_id`
  - latest semantic regime
  - confidence
  - model family
- runtime persistence is limited to the latest closed-bucket snapshot

Quick verification:

```bash
sqlite3 data/db/d5.db "SELECT run_id, condition_set, status, model_family, confidence FROM condition_scoring_run ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/db/d5.db "SELECT bucket_start_utc, semantic_regime, confidence, blocked_flag FROM condition_global_regime_snapshot_v1 ORDER BY created_at DESC LIMIT 10;"
d5 status
```

Interpretation:

- `long_friendly` and `short_friendly` are advisory regime states
- `risk_off` and `no_trade` are currently treated as blocked semantic states in the scorer
- this is not yet policy authority; it is a bounded condition truth surface only

## Step 4. Run The Shadow-Only Ensemble

```bash
d5 run-shadow intraday-meta-stack-v1
```

Expected outcome:

- the command prints a success line with:
  - `experiment_run.run_id`
  - artifact directory
  - Chronos status
- `experiment_run` and `experiment_metric` rows are written
- artifacts are written under `data/research/shadow_runs/<run_id>/`

Quick verification:

```bash
sqlite3 data/db/d5.db "SELECT run_id, experiment_name, status, started_at, finished_at FROM experiment_run ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/db/d5.db "SELECT experiment_run_id, metric_name, metric_value FROM experiment_metric ORDER BY recorded_at DESC LIMIT 20;"
find data/research/shadow_runs -maxdepth 2 -type f | sort
```

Notes:

- the shadow lane uses point-in-time-safe walk-forward regime history
- Chronos-2 is optional; the shadow run may still succeed when Chronos is unavailable
- Fibonacci is a research annotation only, not a runtime gate

## Step 5. Optional DuckDB Sync

```bash
d5 sync-duckdb ingest_run source_health_event token_registry token_price_snapshot quote_snapshot \
  feature_materialization_run feature_spot_chain_macro_minute_v1 feature_global_regime_input_15m_v1 \
  condition_scoring_run condition_global_regime_snapshot_v1 experiment_run experiment_metric
```

## Failure Triage

### Feature materialization fails

Typical causes:

- required lanes are stale or degraded
- canonical truth is too sparse for the requested feature set

What to inspect:

```bash
d5 status
sqlite3 data/db/d5.db "SELECT provider, capture_type, lane_state, checked_at FROM source_health_event ORDER BY checked_at DESC LIMIT 20;"
sqlite3 data/db/d5.db "SELECT run_id, feature_set, status, error_message FROM feature_materialization_run ORDER BY created_at DESC LIMIT 10;"
```

Likely fix:

- refresh the missing source lanes
- rerun the failed feature materialization command

### Condition scoring fails

Typical causes:

- no successful `global-regime-inputs-15m-v1` feature run exists
- not enough 15-minute rows exist to satisfy the training window minimum

What to inspect:

```bash
sqlite3 data/db/d5.db "SELECT run_id, feature_set, status, row_count FROM feature_materialization_run WHERE feature_set = 'global_regime_inputs_15m_v1' ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/db/d5.db "SELECT run_id, condition_set, status, error_message FROM condition_scoring_run ORDER BY created_at DESC LIMIT 10;"
d5 status
```

Likely fix:

- rerun `d5 materialize-features global-regime-inputs-15m-v1`
- make sure enough recent 15-minute market rows exist

### Shadow run fails

Typical causes:

- no successful `spot-chain-macro-v1` feature run exists
- no 5-minute market bars can be built from current truth
- the joined shadow dataset is too small

What to inspect:

```bash
sqlite3 data/db/d5.db "SELECT run_id, feature_set, status, row_count FROM feature_materialization_run WHERE feature_set = 'spot_chain_macro_v1' ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/db/d5.db "SELECT run_id, experiment_name, status, conclusion FROM experiment_run ORDER BY created_at DESC LIMIT 10;"
```

Likely fix:

- refresh Coinbase market-data lanes
- rerun the two feature materializers
- rerun `d5 score-conditions global-regime-v1`
- rerun `d5 run-shadow intraday-meta-stack-v1`

## Not Yet Safe To Claim

This runbook does not imply:

- policy eligibility
- a hard risk gate
- paper-session ownership
- paper fills
- governed model promotion
- live trading

The truthful current claim is narrower:

- source truth exists
- deterministic feature lanes exist
- one bounded condition scorer exists
- one bounded, research-only shadow lane exists
