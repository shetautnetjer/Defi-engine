# D5 Trading Engine PRD

## Document Status

- status: active
- scope: repo-current product requirements
- authority: descriptive of current and near-term repo truth, not a live-trading mandate

## Product Intent

`Defi-engine` is a paper-first crypto data capture and research engine. Its job is to collect, normalize, and preserve market, chain, and macro inputs in auditable storage layers so later feature, condition, policy, and settlement work can be built on stable evidence.

The current product phase is a pre-conditions phase:
- make provider surfaces truthful
- pin the tracked universe to explicit contracts
- preserve raw receipts
- materialize canonical tables with stable UTC timing
- keep downstream trading logic out of scope until the ingest surface is dependable

## Goals

- Provide a canonical write authority in SQLite for paper-first ingestion.
- Preserve replayable raw provider receipts in JSONL and provider-specific raw SQL when needed.
- Support research and backtest workflows through an on-demand DuckDB mirror.
- Establish source-aware seams for:
  - Jupiter spot metadata, prices, and quotes
  - Helius tracked-address discovery and bounded chain-event projection
  - Coinbase public market-data capture
  - FRED macro data
- Keep runtime authority explicit:
  - source -> normalize -> truth -> analytics
- Materialize event timing in UTC with enough structure for later intraday and session analysis.

## Non-Goals

- Live trading
- Wallet signing
- Perps
- Strategy execution
- Paper-fill simulation in the current slice
- Promotion-sensitive model governance
- Deep chain decoding across arbitrary programs

## Product Scope

### In Scope Now

- Config/common helpers
- Alembic-driven canonical schema management
- Raw JSONL landing zone under `data/raw/`
- Canonical SQLite truth DB at `data/db/d5.db`
- DuckDB research mirror at `data/db/d5_analytics.duckdb`
- Separate Coinbase raw DB at `data/db/coinbase_raw.db`
- Generic `d5` CLI:
  - `init`
  - `capture`
  - `status`
  - `sync-duckdb`
- Tracked mint universe authority in config
- UTC-stamped canonical event tables

### Deferred But Planned

- Massive historical implementation
- Paper trading fills and slippage simulation
- Condition/risk/settlement runtime behavior
- Deeper Helius program-aware decoding
- Strategy and promotion workflows
- Provider-specific top-level CLI commands
- `doctor`

## Users

- Operator maintaining the paper-first ingest and research stack
- Research workflows that need canonical market, macro, and chain evidence
- Future downstream engine layers that will consume canonical truth tables rather than direct provider payloads

## Current Source Roles

- Jupiter
  - spot token universe, prices, and quote-quality capture
- Helius
  - on-chain tracked-address discovery and bounded transfer events
- Coinbase
  - public spot market-data for candles, recent trades, and L2 snapshots
- FRED
  - macro reference series and observations
- Massive
  - deferred historical depth source, currently fail-closed

## Tracked Universe

The active Solana spot universe is pinned to exact mints:

- `SOL` = `So11111111111111111111111111111111111111112`
- `USDC` = `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`
- `ZEUS` = `ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq`
- `JUP` = `JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN`
- `BONK` = `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263`
- `zBTC` = `zBTCug3er3tLyffELcvDNrKkCymbPWysGcWihESYfLg`
- `HYPE` = `98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g`
- `OPENAI` = `PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF`

## Functional Requirements

### FR1. Source Capture

The system must capture provider data through explicit adapter clients and record ingest lineage with `ingest_run`.

### FR2. Raw Preservation

The system must preserve raw provider payloads:
- JSONL files under provider/date partitions
- raw truth-table receipts for the active providers
- separate Coinbase raw SQL storage for Coinbase payloads

### FR3. Canonical Normalization

The system must project source-specific payloads into canonical shared tables that are queryable by later layers.

### FR4. Time Discipline

The system must store:
- `captured_at_utc`
- `source_event_time_utc` when present
- derived UTC helper fields:
  - `event_date_utc`
  - `hour_utc`
  - `minute_of_day_utc`
  - `weekday_utc`

### FR5. Provider Truthfulness

The system must fail clearly when required provider inputs are missing or unsupported, rather than returning misleading pseudo-success.

### FR6. Research Mirror

The system must support copying selected canonical tables into DuckDB for research without making DuckDB a write authority.

## Acceptance Surface

The current product should be considered healthy when:

- `d5 init` applies migrations successfully
- `d5 capture` succeeds for the implemented provider paths
- raw receipts are written
- canonical tables are populated
- source health events are recorded
- `d5 sync-duckdb` can mirror selected canonical tables
- offline-safe tests pass by default

## Near-Term Milestones

1. Source preconditions
   - Jupiter spot-only hardening
   - Helius discovery and bounded transfer projection
   - Coinbase public market-data capture
2. Historical research expansion
   - Massive implementation
   - fixed 12-month development and 3-month blind walk-forward protocol
3. Downstream runtime buildout
   - features
   - condition
   - risk
   - settlement

## References

- [README.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/README.md)
- [docs/task/source_expansion_preconditions.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/source_expansion_preconditions.md)
- [docs/plans/source_expansion_preconditions.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/plans/source_expansion_preconditions.md)
- [docs/plans/historical_research_protocol.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/plans/historical_research_protocol.md)
