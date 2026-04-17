# D5 Trading Engine

Paper-only crypto capture with explicit capture-lane freshness ownership, bounded feature materialization, bounded condition scoring, explicit policy tracing, the first hard risk gate, explicit paper settlement ownership, and shadow-only research.

The north star is a Solana-first backtesting and paper-trading platform that
can classify market direction and regimes, compare strategies under explicit
policy/risk/settlement governance, and widen into Jupiter perps and Coinbase
futures only through governed capability stages.

The current repo truth is a paper-first evidence engine with bounded downstream layers:
- implemented now: config/common helpers, raw JSONL storage, SQLite truth models, DuckDB mirror, adapter clients, capture runner, a shared capture-lane status owner (`capture/lane_status.py`), the generic `d5` CLI with per-lane freshness output, two freshness-gated feature lanes (`spot_chain_macro_v1`, `global_regime_inputs_15m_v1`), one bounded regime scorer (`global_regime_v1`), one explicit policy trace owner (`global_regime_v1` -> `policy_global_regime_trace_v1`), one explicit risk gate owner (`RiskGate` -> `risk_global_regime_gate_v1`), one quote-backed paper settlement owner (`PaperSettlement` -> `paper_session`, `paper_fill`, `paper_position`, `paper_session_report`), and one bounded shadow lane (`intraday_meta_stack_v1`)
- active now: mint-locked universe control, Jupiter spot quote hardening, bounded Helius projection, Coinbase market-data capture, and point-in-time-safe regime history for shadow evaluation
- still deferred: runtime-owned execution-intent routing between risk and settlement, governed model promotion, deep Helius decoding, and real Massive historical ingest

Accepted work should also flow through writer-owned truth curation so the full
docs surface, `prd.json`, and `progress.txt` stay aligned, and the next bounded
stories come from receipt-backed findings rather than raw research drift.

No live trading. No wallet signing. No perps.

## Current Architecture

```text
Adapter clients -> CaptureRunner -> Raw JSONL + raw SQL receipts -> source normalizers ->
canonical SQLite truth -> bounded feature materialization -> bounded condition scoring ->
explicit policy tracing -> explicit risk gating -> explicit paper settlement + bounded shadow evaluation ->
DuckDB sync on demand + research artifacts
```

- `data/raw/{provider}/{YYYY-MM-DD}/` is the raw landing zone
- `data/db/d5.db` is the canonical SQLite write surface
- `data/db/d5_analytics.duckdb` is the research mirror
- `data/db/coinbase_raw.db` is a separate raw provider store for Coinbase payloads

See [docs/README.md](docs/README.md) for the full docs map, [docs/prd/crypto_backtesting_mission.md](docs/prd/crypto_backtesting_mission.md) for the north-star product target, [docs/plans/strategy_descent_and_instrument_scope.md](docs/plans/strategy_descent_and_instrument_scope.md) for the widening ladder, [docs/math/market_regime_forecast_and_labeling_program.md](docs/math/market_regime_forecast_and_labeling_program.md) for the future math program, [docs/policy/runtime_authority_and_promotion_ladder.md](docs/policy/runtime_authority_and_promotion_ladder.md) for promotion doctrine, [docs/policy/writer_story_promotion_rubric.md](docs/policy/writer_story_promotion_rubric.md) for writer-owned story curation, [docs/architecture/bootstrap_architecture.md](docs/architecture/bootstrap_architecture.md) for the current architecture write-up, [docs/math/regime_shadow_modeling_contracts.md](docs/math/regime_shadow_modeling_contracts.md) for the bounded current modeling contract, and [docs/runbooks/ralph_tmux_swarm.md](docs/runbooks/ralph_tmux_swarm.md) for the repo-local four-lane orchestration workflow.

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
d5 capture fred-observations

# first bounded post-ingest feature lane
d5 materialize-features spot-chain-macro-v1
d5 materialize-features global-regime-inputs-15m-v1

# first bounded condition lane
d5 score-conditions global-regime-v1

# first bounded shadow lane
d5 run-shadow intraday-meta-stack-v1

# optional: sync canonical tables into DuckDB
d5 sync-duckdb ingest_run source_health_event token_registry token_price_snapshot quote_snapshot \
  feature_materialization_run feature_spot_chain_macro_minute_v1 feature_global_regime_input_15m_v1 \
  condition_scoring_run condition_global_regime_snapshot_v1 policy_global_regime_trace_v1 \
  risk_global_regime_gate_v1 paper_session paper_fill paper_position paper_session_report \
  experiment_run experiment_metric experiment_realized_feedback_v1
```

## Current CLI Surface

| Command | Action |
|---------|--------|
| `d5 init` | Apply Alembic migrations to the canonical SQLite truth database |
| `d5 capture <provider|all>` | Run one capture flow using the current generic dispatcher |
| `d5 materialize-features <feature-set>` | Materialize a bounded deterministic feature set from canonical truth |
| `d5 score-conditions <condition-set>` | Score a bounded condition set from deterministic feature inputs |
| `d5 run-shadow <shadow-run>` | Run a bounded shadow-only ML evaluation lane |
| `d5 status` | Show recent ingest runs, latest provider health events, per-lane capture freshness, and the latest condition run |
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
| Helius | partial | tracked-address discovery, enhanced transaction capture, bounded `solana_transfer_event` projection, and hardened raw websocket capture with reconnect / heartbeat |
| Coinbase | partial | public product, candle, trade, and L2 book capture with separate raw DB and canonical market-data tables |
| FRED | implemented | series and observation capture/normalization |
| Massive | scaffolded | fail-closed readiness/probe path until entitlement and payload shape are confirmed |

## Bounded Model Surfaces

- `spot_chain_macro_v1`
  - minute-by-mint feature lane from canonical spot, market-structure, chain, and macro truth
- `global_regime_inputs_15m_v1`
  - market-wide 15-minute feature lane built from Coinbase proxy products plus captured-at-safe macro context
- `global_regime_v1`
  - bounded regime scorer with a four-state Gaussian HMM when `hmmlearn` is installed and a Gaussian-mixture fallback when it is not
- `intraday_meta_stack_v1`
  - shadow-only evaluation lane with walk-forward regime history, ATR-style triple-barrier labels, `IsolationForest`, `RandomForest`, `XGBoost`, optional Chronos-2 summaries, Monte Carlo summaries, and Fibonacci annotations as research-only evidence
- `experiment_realized_feedback_v1`
  - advisory comparison receipts that align replayed shadow context to settlement-owned paper fills and latest session snapshots without promoting research outputs into runtime authority

These surfaces remain non-promoting. The truthful claim is that the repo now has deterministic features, a bounded regime score, explicit policy eligibility traces, one hard risk gate, one quote-backed paper settlement owner, one bounded shadow evaluation lane, and advisory realized-feedback comparison receipts grounded in settlement truth; it does not yet have runtime-owned instrument selection, automatic execution intent routing, or governed model promotion.

## Time Handling

- event-style canonical tables store `captured_at_utc`
- when a provider emits event time, it also stores `source_event_time_utc`
- derived UTC helper fields are stored for later session and intraday analysis:
  - `event_date_utc`
  - `hour_utc`
  - `minute_of_day_utc`
  - `weekday_utc`

## Validation

The repo keeps an offline-safe default test surface for config loading, migration/bootstrap behavior, CLI smoke, mocked adapters, fail-closed capture semantics, and docs truth contracts, plus live-gated Jupiter and Helius integration harnesses for provider receipts. Validation commands are documented in [docs/test/bootstrap_validation.md](docs/test/bootstrap_validation.md).

## Governance

- Paper trading only unless the operator explicitly widens scope.
- SQLite is canonical truth. DuckDB is a research mirror.
- Models suggest; the engine decides; the risk gate is final.
- Current repo truth comes from code, config, schema, docs, and checks in this repo.
- See [AGENTS.md](AGENTS.md) for the operating rules.
