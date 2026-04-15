# D5 Trading Engine PRD

## Document Status

- status: active
- scope: repo-current product requirements
- authority: descriptive of current and near-term repo truth, not a live-trading mandate

## Product Intent

`Defi-engine` is a paper-first crypto data capture, feature, condition, and shadow-research engine. Its job is to collect, normalize, and preserve market, chain, and macro inputs in auditable storage layers, then expose bounded deterministic features, bounded regime scoring, and bounded shadow evaluation without silently widening runtime authority.

The current product phase is no longer source-ingest only. It is a bounded downstream proving phase:
- make provider and freshness surfaces truthful
- preserve replayable raw receipts and canonical truth
- materialize deterministic feature tables from canonical inputs only
- score one bounded global regime condition from feature truth
- run one bounded shadow-only evaluation lane with explicit receipts and research artifacts
- keep policy, risk, settlement, and promotion-sensitive runtime behavior out of scope until they are separately owned

## Goals

- Provide a canonical write authority in SQLite for paper-first ingestion.
- Preserve replayable raw provider receipts in JSONL and provider-specific raw SQL when needed.
- Support research and backtest workflows through an on-demand DuckDB mirror.
- Establish source-aware seams for:
  - Jupiter spot metadata, prices, and quotes
  - Helius tracked-address discovery and bounded chain-event projection
  - Coinbase public market-data capture
  - FRED macro data
- Establish deterministic downstream seams for:
  - `spot_chain_macro_v1`
  - `global_regime_inputs_15m_v1`
  - `global_regime_v1`
  - `intraday_meta_stack_v1`
- Keep runtime authority explicit:
  - source -> normalize -> truth -> features -> condition -> shadow evidence
- Preserve auditable receipts for feature, condition, and shadow runs.

## Non-Goals

- Live trading
- Wallet signing
- Perps
- Strategy execution
- Policy-driven order eligibility in the current slice
- Hard risk gating in the current slice
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
  - `materialize-features`
  - `score-conditions`
  - `run-shadow`
  - `status`
  - `sync-duckdb`
- Tracked mint universe authority in config
- UTC-stamped canonical event tables
- Two bounded deterministic feature sets:
  - `spot_chain_macro_v1`
  - `global_regime_inputs_15m_v1`
- One bounded condition scorer:
  - `global_regime_v1`
- One bounded shadow-only ensemble:
  - `intraday_meta_stack_v1`

### Deferred But Planned

- Real `policy/` ownership of eligibility and decision traces
- Real `risk/` veto surfaces
- Real `settlement/` paper-session receipts and performance accounting
- Governed model promotion
- Massive historical implementation
- Deeper Helius program-aware decoding
- Strategy and paper-session workflows
- Provider-specific top-level CLI commands
- `doctor`

## Users

- Operator maintaining the paper-first ingest and research stack
- Research workflows that need canonical market, macro, and chain evidence
- Future downstream engine layers that will consume feature truth, condition truth, and experiment receipts rather than direct provider payloads

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

### FR4. Deterministic Feature Truth

The system must materialize bounded feature tables from canonical truth only, with freshness qualification captured in `feature_materialization_run`.

### FR5. Time Discipline

The system must store:
- `captured_at_utc`
- `source_event_time_utc` when present
- derived UTC helper fields:
  - `event_date_utc`
  - `hour_utc`
  - `minute_of_day_utc`
  - `weekday_utc`

Macro context used in feature rows must be available by `captured_at` at the relevant feature bucket, not merely by `observation_date`.

### FR6. Bounded Condition Scoring

The system must support one bounded regime scorer that:
- consumes `global_regime_inputs_15m_v1`
- emits a latest condition receipt in `condition_scoring_run`
- emits a latest closed-bucket snapshot in `condition_global_regime_snapshot_v1`
- remains explicit about model family and fallback path

### FR7. Shadow-Only Evaluation

The system must support one bounded shadow lane that:
- uses point-in-time-safe walk-forward regime history
- records experiment receipts in `experiment_run` and `experiment_metric`
- writes research artifacts under `data/research/shadow_runs/`
- does not promote its outputs into policy or trading authority

### FR8. Provider Truthfulness

The system must fail clearly when required provider or freshness inputs are missing or unsupported, rather than returning misleading pseudo-success.

### FR9. Research Mirror

The system must support copying selected canonical tables into DuckDB for research without making DuckDB a write authority.

## Acceptance Surface

The current product should be considered healthy when:

- `d5 init` applies migrations successfully
- `d5 capture` succeeds for the implemented provider paths
- raw receipts are written
- canonical tables are populated
- source health events are recorded
- `d5 materialize-features spot-chain-macro-v1` succeeds when required lanes are fresh
- `d5 materialize-features global-regime-inputs-15m-v1` succeeds when required market lanes are fresh
- `d5 score-conditions global-regime-v1` writes a latest condition receipt and snapshot
- `d5 run-shadow intraday-meta-stack-v1` writes experiment receipts and artifacts
- `d5 status` shows the latest condition run, including failed-run visibility
- `d5 sync-duckdb` can mirror selected canonical, feature, condition, and experiment tables
- offline-safe tests pass by default

## Near-Term Milestones

1. Source truth and continuous capture ownership
   - Jupiter spot-only hardening
   - Helius discovery and bounded transfer projection
   - Coinbase public market-data capture
2. Bounded downstream proving
   - deterministic feature lanes
   - bounded global regime scoring
   - point-in-time-safe shadow evaluation
3. Runtime ownership buildout
   - policy
   - risk
   - settlement
4. Broader research and model governance
   - trajectory and scenario surfaces
   - promotion-sensitive evaluation rules
   - historical source expansion

## References

- [README.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/README.md)
- [docs/task/first_feature_input_contract.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/first_feature_input_contract.md)
- [docs/task/global_regime_condition_and_shadow_stack.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/global_regime_condition_and_shadow_stack.md)
- [docs/plans/build_sequence_and_runtime_ownership.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/plans/build_sequence_and_runtime_ownership.md)
- [docs/plans/historical_research_protocol.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/plans/historical_research_protocol.md)
- [docs/math/regime_shadow_modeling_contracts.md](/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/math/regime_shadow_modeling_contracts.md)
