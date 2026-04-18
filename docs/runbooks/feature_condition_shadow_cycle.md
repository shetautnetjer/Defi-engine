# Feature, Condition, And Shadow Cycle Runbook

Operator path for the current downstream loop after source capture is already working.

## Purpose

Run the bounded downstream stack in the intended order:

1. verify source freshness
2. optionally backfill the bounded Massive historical ladder
3. materialize deterministic features
4. score the bounded global regime
5. run the bounded shadow-only ensemble
6. optionally run the live intraday regime cycle
7. inspect receipts and artifacts without widening runtime authority

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

For the historical ladder, the repo now also supports bounded Massive free-tier
minute history:

- `d5 capture massive-minute-aggs --full-free-tier`
- the free-tier assumption is currently a 2-year minute-history window
- only `X:SOLUSD`, `X:BTCUSD`, and `X:ETHUSD` are normalized into canonical SQL
- raw `.csv.gz` files are preserved for replay

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

Optional bounded historical backfill before downstream scoring:

```bash
d5 capture massive-minute-aggs --full-free-tier
```

Or use an explicit historical range:

```bash
d5 capture massive-minute-aggs --from 2024-04-18 --to 2026-04-16
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
- the regime lane prefers Coinbase candles when available and falls back to
  Massive candles for the proxy symbols when Coinbase history is absent

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
d5 run-shadow regime-model-compare-v1
```

Historical bounded comparison example:

```bash
d5 run-shadow regime-model-compare-v1 --history-start 2024-04-18 --history-end 2026-04-16 --use-massive-context
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
- `regime-model-compare-v1` is a separate shadow lane that compares HMM, GMM,
  and an optional `statsmodels` candidate on the canonical 15-minute feature
  truth, then writes advisory-only proposal evidence instead of changing the
  regime owner

## Step 5. Optional Live Intraday Training Cycle

```bash
d5 run-live-regime-cycle
```

Optional bounded websocket burst:

```bash
d5 run-live-regime-cycle --with-helius-ws
```

Expected outcome:

- live capture receipts are written for Jupiter, Helius, and Coinbase
- `spot_chain_macro_v1` and `global_regime_inputs_15m_v1` are rematerialized
- `global_regime_v1` is rescored
- `regime-model-compare-v1` is rerun on the latest trailing window
- policy and risk are re-evaluated
- a paper-ready receipt is written under the live-cycle artifact directory

Important:

- this command does not place a paper trade by itself
- it prepares the bounded evidence and freshest quote snapshot so the operator
  can explicitly run the next paper cycle

Typical explicit follow-up:

```bash
d5 run-paper-cycle <quote_snapshot_id> --condition-run-id <condition_run_id> --strategy-report <path>
```

## Step 6. Optional DuckDB Sync

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
- rerun `d5 run-shadow regime-model-compare-v1` only after the bounded feature
  history is deep enough for comparison

### Live regime cycle fails

Typical causes:

- one of the live capture lanes is degraded or stale
- no eligible `USDC -> SOL` Jupiter quote snapshot exists for the paper-ready
  receipt
- policy or risk is not in an eligible state

What to inspect:

```bash
d5 status
sqlite3 data/db/d5.db "SELECT run_id, provider, capture_type, status FROM ingest_run ORDER BY created_at DESC LIMIT 20;"
find data/research/live_regime_cycle -maxdepth 2 -type f | sort
```

Likely fix:

- refresh the failing capture lane explicitly
- rerun `d5 run-live-regime-cycle`
- only invoke `d5 run-paper-cycle ...` after the paper-ready receipt says the
  quote/policy/risk tuple is ready

## Not Yet Safe To Claim

This runbook does not imply:

- governed model promotion
- live trading

The truthful current claim is:

- policy eligibility now exists through explicit policy traces
- a hard risk gate now exists through explicit risk verdicts
- paper sessions and paper fills now exist through settlement-owned paper
  receipts
- shadow outputs and realized-feedback remain advisory rather than promotional

- source truth exists
- deterministic feature lanes exist
- one bounded condition scorer exists
- one bounded, research-only shadow lane exists
