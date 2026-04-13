# D5 Trading Engine

Paper-only crypto data capture and research bootstrap.

The current repo truth is a pre-conditions ingest engine:
- implemented now: config/common helpers, raw JSONL storage, SQLite truth models, DuckDB mirror, adapter clients, capture runner, normalizers, and the generic `d5` CLI
- active now: mint-locked universe control, Jupiter spot quote hardening, bounded Helius projection, and Coinbase market-data capture
- still deferred: perps, live order routing, paper fill simulation, deep Helius decoding, and real Massive historical ingest

No live trading. No wallet signing. No perps.

## Current Architecture

```text
Adapter clients -> CaptureRunner -> Raw JSONL + raw SQL receipts -> source normalizers ->
canonical SQLite truth -> DuckDB sync on demand
```

- `data/raw/{provider}/{YYYY-MM-DD}/` is the raw landing zone
- `data/db/d5.db` is the canonical SQLite write surface
- `data/db/d5_analytics.duckdb` is the research mirror
- `data/db/coinbase_raw.db` is a separate raw provider store for Coinbase payloads

See [docs/README.md](docs/README.md) for the full docs map and [docs/architecture/bootstrap_architecture.md](docs/architecture/bootstrap_architecture.md) for the current architecture write-up.

## Tracked Universe

The current mint-locked Solana spot universe is:

- `SOL` = `So11111111111111111111111111111111111111112`
- `USDC` = `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- `ZEUS` = `ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq`
- `JUP` = `JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN`
- `BONK` = `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`
- `zBTC` = `zBTCug3er3tLyffELcvDNrKkCymbPWysGcWihESYfLg`
- `HYPE` = `98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g`
- `OPENAI` = `PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF`

## Quick Start

```bash
cd Defi-engine
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env
# fill in the provider keys you plan to use
# set HELIUS_TRACKED_ADDRESSES for Helius capture
# optionally point COINBASE_SECRETS_FILE at a local secrets file

d5 init
d5 status

# safe first captures
d5 capture jupiter-tokens
d5 capture jupiter-prices
d5 capture jupiter-quotes
d5 capture helius-discovery
d5 capture coinbase-products

# optional: sync canonical tables into DuckDB
d5 sync-duckdb ingest_run source_health_event token_registry token_price_snapshot quote_snapshot
```

## Current CLI Surface

| Command | Action |
|---------|--------|
| `d5 init` | Apply Alembic migrations to the canonical SQLite truth database |
| `d5 capture <provider|all>` | Run one capture flow using the current generic dispatcher |
| `d5 status` | Show recent ingest runs and latest provider health events |
| `d5 sync-duckdb [tables...]` | Copy selected SQLite truth tables into DuckDB |

Current `capture` provider values:
- `jupiter-tokens`
- `jupiter-prices`
- `jupiter-quotes`
- `helius-transactions`
- `helius-discovery`
- `helius-ws-events`
- `coinbase-products`
- `coinbase-candles`
- `coinbase-market-trades`
- `coinbase-book`
- `fred-series`
- `fred-observations`
- `massive-crypto`
- `all`

## Source Status

| Provider | Status | Notes |
|----------|--------|-------|
| Jupiter | implemented | spot-only token list, prices, and two-sided quote capture with default `2.0s` throttling |
| Helius | partial | tracked-address discovery, enhanced transaction capture, bounded `solana_transfer_event` projection, and raw websocket capture |
| Coinbase | partial | public product, candle, trade, and L2 book capture with separate raw DB and canonical market-data tables |
| FRED | implemented | series and observation capture/normalization |
| Massive | scaffolded | fail-closed readiness/probe path until entitlement and payload shape are confirmed |

## Time Handling

- event-style canonical tables store `captured_at_utc`
- when a provider emits event time, it also stores `source_event_time_utc`
- derived UTC helper fields are stored for later session and intraday analysis:
  - `event_date_utc`
  - `hour_utc`
  - `minute_of_day_utc`
  - `weekday_utc`

## Validation

The repo keeps an offline-safe default test surface for config loading, migration/bootstrap behavior, CLI smoke, mocked adapters, fail-closed capture semantics, and docs truth contracts, plus a live-gated Jupiter integration harness for tokens + prices. Validation commands are documented in [docs/test/bootstrap_validation.md](docs/test/bootstrap_validation.md).

## Governance

- Paper trading only unless the operator explicitly widens scope.
- SQLite is canonical truth. DuckDB is a research mirror.
- Models suggest; the engine decides; the risk gate is final.
- Current repo truth comes from code, config, schema, docs, and checks in this repo.
- See [AGENTS.md](AGENTS.md) for the operating rules.
