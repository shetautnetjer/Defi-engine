# First Capture Runbook

Operator path for the first local bootstrap capture.

## Prerequisites

- Python 3.12+
- a virtualenv or other isolated Python environment
- `.env` created from `.env.example`
- provider keys filled in for the captures you actually plan to run

Notes:

- `Jupiter` captures require `JUPITER_API_KEY`
- `FRED` captures require `FRED_API_KEY`
- `Helius` transaction capture also requires tracked addresses to be configured
- `Massive` is currently scaffold-only and should be expected to fail closed

## Setup

```bash
cd /home/netjer/Projects/AI-Frame/Brain/Defi-engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Initialize The Local Data Surfaces

```bash
d5 init
d5 status
```

Expected outcome:

- `d5 init` applies Alembic migrations to the canonical SQLite truth database
- `data/db/d5.db` is created
- `data/db/d5_analytics.duckdb` is not created until you sync DuckDB
- `data/raw/` and `data/parquet/` provider directories are created
- `d5 status` may still show no ingest runs if you have not captured anything yet

## Safe First Captures

Start with captures that do not require tracked Solana addresses:

```bash
d5 capture fred-series
d5 capture fred-observations
d5 capture jupiter-tokens
d5 capture jupiter-prices
```

Optional captures:

```bash
d5 capture jupiter-quotes
d5 capture helius-transactions
```

Use Helius only after configuring tracked addresses in settings or environment. Massive is not part of the safe-first path yet.

## Sync Into DuckDB

```bash
d5 sync-duckdb ingest_run fred_series_registry fred_observation token_registry token_price_snapshot
```

## Inspect Raw Files

```bash
find data/raw -maxdepth 3 -type f | sort
```

You should see JSONL files partitioned by provider and date.

## Inspect SQLite Truth

```bash
sqlite3 data/db/d5.db ".tables"
sqlite3 data/db/d5.db "SELECT run_id, provider, capture_type, status FROM ingest_run ORDER BY created_at DESC LIMIT 10;"
sqlite3 data/db/d5.db "SELECT count(*) FROM fred_series_registry;"
sqlite3 data/db/d5.db "SELECT count(*) FROM fred_observation;"
sqlite3 data/db/d5.db "SELECT count(*) FROM token_registry;"
sqlite3 data/db/d5.db "SELECT count(*) FROM token_price_snapshot;"
```

## Inspect DuckDB Mirror

If the DuckDB CLI is installed:

```bash
duckdb data/db/d5_analytics.duckdb "SHOW TABLES;"
duckdb data/db/d5_analytics.duckdb "SELECT count(*) FROM fred_observation;"
duckdb data/db/d5_analytics.duckdb "SELECT count(*) FROM token_registry;"
```

If you do not have the DuckDB CLI installed, use Python:

```bash
python - <<'PY'
import duckdb
db = duckdb.connect("data/db/d5_analytics.duckdb")
print(db.sql("SHOW TABLES").fetchall())
print(db.sql("SELECT count(*) FROM fred_observation").fetchall())
PY
```

## Failure Triage

- If `d5 init` fails, inspect `.env`, Python dependencies, Alembic configuration, and filesystem permissions under `data/`.
- If a capture fails, check that the required API key is set and retry one provider at a time.
- If DuckDB sync fails, confirm that the referenced SQLite tables exist first.
