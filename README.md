# D5 Trading Engine

Paper-only crypto capture with explicit capture-lane freshness ownership, bounded feature materialization, bounded condition scoring, explicit policy tracing, the first hard risk gate, explicit paper settlement ownership, explicit spot-first backtest truth, and shadow-only research.

The north star is a Solana-first backtesting and paper-trading platform that
can classify market direction and regimes, compare strategies under explicit
policy/risk/settlement governance, and widen into Jupiter perps and Coinbase
futures only through governed capability stages.

The current repo truth is a paper-first evidence engine with bounded downstream layers:
- implemented now: config/common helpers, raw JSONL storage, SQLite truth models, DuckDB mirror, adapter clients, capture runner, a shared capture-lane status owner (`capture/lane_status.py`), the generic `d5` CLI with per-lane freshness output, two freshness-gated feature lanes (`spot_chain_macro_v1`, `global_regime_inputs_15m_v1`), one bounded regime scorer (`global_regime_v1`), one explicit policy trace owner (`global_regime_v1` -> `policy_global_regime_trace_v1`), one explicit risk gate owner (`RiskGate` -> `risk_global_regime_gate_v1`), one explicit execution-intent owner (`ExecutionIntentOwner` -> `execution_intent_v1`), one quote-backed paper settlement owner (`PaperSettlement` -> `paper_session`, `paper_fill`, `paper_position`, `paper_session_report`), one settlement-owned spot-first backtest replay owner (`BacktestTruthOwner` -> `backtest_session_v1`, `backtest_fill_v1`, `backtest_position_v1`, `backtest_session_report_v1`), one bounded shadow lane (`intraday_meta_stack_v1`), one canonical label-program lane (`label_program_v1`), one governed strategy challenger lane (`strategy_eval_v1`), one centralized reporting layer (`reporting/`), proposal truth tables (`artifact_reference`, `improvement_proposal_v1`), proposal review/comparison truth (`proposal_review_v1`, `proposal_comparison_v1`, `proposal_comparison_item_v1`, `proposal_supersession_v1`), and first-pass Massive reference plus historical minute-aggregate capture
- active now: mint-locked universe control, Jupiter spot quote hardening, bounded Helius projection, Coinbase market-data capture, and point-in-time-safe regime history for shadow evaluation
- still deferred: canonical label/regime truth, strategy registry and challenger governance, governed model promotion, deep Helius decoding, and broader Massive entitlement coverage

Accepted work should also flow through writer-owned truth curation so the full
docs surface, `prd.json`, and `progress.txt` stay aligned, and the next bounded
stories come from receipt-backed findings rather than raw research drift.

No live trading. No wallet signing. No perps.

## Current Architecture

```text
Adapter clients -> CaptureRunner -> raw JSONL / CSV.gz source artifacts + Parquet warehouse ->
canonical SQLite truth -> bounded feature materialization -> bounded condition scoring ->
explicit policy tracing -> explicit risk gating -> explicit paper settlement + bounded shadow evaluation ->
DuckDB sync on demand + research artifacts
```

- `data/raw/{provider}/{YYYY-MM-DD}/` is the raw landing zone for JSONL and CSV.gz source artifacts
- `data/parquet/` is the partitioned deep-history warehouse for replay and walk-forward reads
- `data/db/d5.db` is the canonical SQLite write surface
- `data/db/d5_analytics.duckdb` is the research mirror
- `data/db/coinbase_raw.db` is a separate raw provider store for Coinbase payloads

See [docs/README.md](docs/README.md) for the full docs map, [docs/prd/crypto_backtesting_mission.md](docs/prd/crypto_backtesting_mission.md) for the north-star product target, [docs/plans/strategy_descent_and_instrument_scope.md](docs/plans/strategy_descent_and_instrument_scope.md) for the widening ladder, [docs/math/market_regime_forecast_and_labeling_program.md](docs/math/market_regime_forecast_and_labeling_program.md) for the future math program, [docs/policy/runtime_authority_and_promotion_ladder.md](docs/policy/runtime_authority_and_promotion_ladder.md) for promotion doctrine, [docs/policy/writer_story_promotion_rubric.md](docs/policy/writer_story_promotion_rubric.md) for writer-owned story curation, [docs/architecture/bootstrap_architecture.md](docs/architecture/bootstrap_architecture.md) for the current architecture write-up, [docs/math/regime_shadow_modeling_contracts.md](docs/math/regime_shadow_modeling_contracts.md) for the bounded current modeling contract, [docs/runbooks/ralph_tmux_swarm.md](docs/runbooks/ralph_tmux_swarm.md) for the repo-local four-lane orchestration workflow, and [docs/task/trading_qmd_report_contract.md](docs/task/trading_qmd_report_contract.md) for the standardized trading evidence packet contract.

Project Notion surfaces:

- [Defi-engine project hub](https://www.notion.so/Defi-engine-342936b02c2580bc8062f70287d6919c?source=copy_link)
- [CLI Ideas review page](https://www.notion.so/CLI-Ideas-346936b02c258037a00ffdcc53f4693a?source=copy_link)
- [Codex trader harnesses review page](https://www.notion.so/Codex-trader-harnesses-347936b02c25806bad8bd6a5fde8c51d?source=copy_link)

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
# optionally point COINBASE_SECRETS_FILE at either:
# - a legacy Coinbase Exchange KEY/SECRET/PASSPHRASE env file, or
# - a Coinbase CDP/Coinbase App key export with the API key name + ECDSA private key

d5 init
d5 status

# safe first captures
d5 capture jupiter-tokens
d5 capture jupiter-prices
d5 capture jupiter-quotes
d5 capture helius-discovery
d5 capture coinbase-products
d5 capture fred-observations
d5 capture massive-crypto
d5 capture massive-minute-aggs --date 2026-04-16
d5 capture massive-minute-aggs --full-free-tier

# first bounded post-ingest feature lane
d5 materialize-features spot-chain-macro-v1
d5 materialize-features global-regime-inputs-15m-v1

# first bounded condition lane
d5 score-conditions global-regime-v1

# first bounded shadow lane
d5 run-shadow intraday-meta-stack-v1

# bounded shadow regime-model comparison lane
d5 run-shadow regime-model-compare-v1

# repo-owned training wrappers for automation and review
d5 hydrate-history --training-regimen auto --json
d5 training bootstrap --json
d5 training hydrate-history --training-regimen auto --json
d5 training collect --json
d5 training walk-forward --training-regimen auto --json
d5 training review --json
d5 training loop --max-iterations 1 --json
d5 training status --json
d5 training evidence-gap --json
d5 diagnose training-window --regimen quickstart_300d --json
d5 diagnose gate-funnel --run latest --json
d5 diagnose no-trades --run latest --window 300d --json

# live intraday training cycle for paper trading
d5 run-live-regime-cycle

# explicit paper cycle from the live-cycle paper-ready receipt
d5 run-paper-cycle <quote_snapshot_id> --condition-run-id <condition_run_id> --strategy-report <path>

# bounded autonomous paper-practice ladder
d5 run-paper-practice-bootstrap
d5 run-paper-practice-loop --max-iterations 1
d5 paper-practice-status
d5 run-paper-close <session_key> --quote-snapshot-id <quote_snapshot_id> --reason take_profit

# optional: sync canonical tables into DuckDB
  d5 sync-duckdb ingest_run source_health_event token_registry token_price_snapshot quote_snapshot \
  feature_materialization_run feature_spot_chain_macro_minute_v1 feature_global_regime_input_15m_v1 \
  condition_scoring_run condition_global_regime_snapshot_v1 policy_global_regime_trace_v1 \
  risk_global_regime_gate_v1 execution_intent_v1 paper_session paper_fill paper_position paper_session_report \
  backtest_session_v1 backtest_fill_v1 backtest_position_v1 backtest_session_report_v1 \
  experiment_run experiment_metric experiment_realized_feedback_v1 artifact_reference improvement_proposal_v1
```

## Current CLI Surface

| Command | Action |
|---------|--------|
| `d5 init` | Apply Alembic migrations to the canonical SQLite truth database |
| `d5 capture <provider|all>` | Run one capture flow using the current generic dispatcher |
| `d5 materialize-features <feature-set>` | Materialize a bounded deterministic feature set from canonical truth |
| `d5 score-conditions <condition-set>` | Score a bounded condition set from deterministic feature inputs |
| `d5 run-shadow <shadow-run>` | Run a bounded shadow-only ML evaluation lane |
| `d5 run-label-program <label-program>` | Run the bounded canonical label-program scoring loop |
| `d5 run-strategy-eval <strategy-eval>` | Run the bounded named strategy challenger loop |
| `d5 run-paper-close <session_key> --quote-snapshot-id <id> --reason <reason>` | Close one open paper session from an explicit exit quote |
| `d5 run-paper-practice-bootstrap` | Build the bounded historical bootstrap for autonomous paper practice |
| `d5 hydrate-history --training-regimen <auto|quickstart_300d|full_730d>` | Hydrate the selected Massive-backed training-regimen window without forcing the full cache first |
| `d5 training bootstrap` | Run the repo-owned training bootstrap wrapper and return machine-readable receipts |
| `d5 training hydrate-history --training-regimen <name>` | Fill the selected training-regimen history window or, without a regimen, the missing full historical backbone |
| `d5 training collect` | Append incremental Massive/Coinbase/Jupiter/Helius source data without repulling cached history |
| `d5 training walk-forward --training-regimen <name>` | Run the repo-owned adaptive historical replay wrapper against a selected regimen |
| `d5 training review` | Render the latest bounded training review packet from existing receipts |
| `d5 training loop` | Run the repo-owned training loop wrapper for bounded autonomous practice iterations |
| `d5 training status` | Show the repo-owned training workspace status and latest active revision |
| `d5 training evidence-gap` | Roll up paper decisions into ranked failure families and the next comparable experiment batch |
| `d5 diagnose training-window` | Review SQL and feature coverage for a selected training regimen |
| `d5 diagnose gate-funnel` | Count paper-practice decisions through condition, policy, risk, quote, and fill stages |
| `d5 diagnose no-trades` | Explain why a selected paper window produced no or few trades |
| `d5 run-paper-practice-loop` | Run the autonomous paper-only practice loop |
| `d5 paper-practice-status` | Show the active paper-practice profile and latest loop state |
| `d5 review-proposal <proposal_id>` | Run the bounded advisory proposal-review workflow and write review truth plus QMD evidence |
| `d5 compare-proposals` | Rank bounded proposals, optionally select the next experiment, and write comparison/supersession truth |
| `d5 run-live-regime-cycle` | Run the live intraday capture -> feature -> regime -> comparison ladder and emit a paper-ready receipt |
| `d5 status` | Show recent ingest runs, latest provider health events, per-lane capture freshness, and the latest condition run |
| `d5 sync-duckdb [tables...]` | Copy selected SQLite truth tables into DuckDB |

Coinbase credential note:
- current capture lanes use Coinbase public market-data endpoints only
- if you later add private Coinbase App / Advanced Trade endpoints, use CDP/Coinbase App JWT auth with an **ECDSA / ES256** key, not Exchange passphrase auth
- if you use `COINBASE_SECRETS_FILE`, the settings layer now understands both the legacy Exchange env-file shape and the simpler CDP/Coinbase App export shape

Paper-practice training regimen note:
- `PAPER_PRACTICE_TRAINING_PROFILE=auto` is the default and picks the fastest ready regimen so paper training can start once `quickstart_300d` is satisfied
- `PAPER_PRACTICE_TRAINING_PROFILE=quickstart_300d` enables an earlier paper-only bootstrap with explicit lower-confidence labeling
- `PAPER_PRACTICE_TRAINING_PROFILE=full_730d` keeps the heavier long-history path available when it is explicitly selected
- these regimens govern history budget and replay shape only; they do not hard-wire strategy, policy, or risk
- `TRADER_RESEARCH_PROFILE=<name>` selects the trader/autoresearch bias pack from `.ai/profiles.toml`
- separate research-bias profiles belong in `.ai/profiles.toml` with `.ai/schemas/profile.schema.json` validation; `training/config/research_profiles.example.toml` remains a companion example
- research-bias profiles describe what hypotheses to explore and how to rank them, not how live runtime authority behaves
- the thin profile governor lives alongside that pack in `.ai/policies/profile_router_policy.v1.json`, `.ai/schemas/meta_governor_scorecard.schema.json`, `.ai/schemas/profile_router_policy.schema.json`, `.ai/schemas/profile_governor_decision.schema.json`, and `.ai/prompts/profile_governor_turn.md`
- the profile governor is a review/router layer over existing evidence, not a runtime strategy or risk authority

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
- `massive-minute-aggs`
- `all`

`massive-minute-aggs` supports three bounded historical modes:
- `--date YYYY-MM-DD`
- `--from YYYY-MM-DD --to YYYY-MM-DD`
- `--full-free-tier`

The intended training cadence is now cache-first:
- hydrate the selected Massive-backed training-regimen window first, for example `quickstart_300d`
- hydrate the full Massive 2-year window only when `full_730d` is explicitly selected or already ready
- preserve raw source artifacts and Parquet partitions for long-horizon replay
- use Massive REST range calls in bounded chunks (`limit=50000` per ticker request) when flat files are unavailable
- reuse local SQL + local warehouse artifacts for backtest and walk-forward
- append only missing/new source data with `d5 training collect`
- run the continuous paper-practice loop only after the selected historical ladder is bootstrapped

Current `run-shadow` values:
- `intraday-meta-stack-v1`
- `regime-model-compare-v1`
  - compares the canonical 15-minute feature truth against HMM, GMM, and an
    optional `statsmodels` candidate
  - supports bounded historical windows via `--history-start` and
    `--history-end`
  - can include or exclude Massive-backed feature rows via
    `--use-massive-context/--no-use-massive-context`
  - writes experiment truth, QMD evidence, and an advisory-only
    `regime_model_compare_follow_on` proposal
  - does not widen policy, risk, execution, settlement, or runtime authority

## Source Status

| Provider | Status | Notes |
|----------|--------|-------|
| Jupiter | implemented | spot-only token list, prices, and two-sided quote capture with default `2.0s` throttling |
| Helius | partial | tracked-address discovery, enhanced transaction capture, bounded `solana_transfer_event` projection, and hardened raw websocket capture with reconnect / heartbeat |
| Coinbase | partial | public product discovery now merges default spot inventory with filtered futures and perpetual inventories for the bounded context set; some non-crypto contracts may expose trades/candles without an L2 book |
| FRED | implemented | series and observation capture/normalization |
| Massive | partial | first-pass crypto reference, snapshots, and historical minute aggregates with canonical SQL normalization plus Parquet warehousing; the runtime prefers flat files when entitled and falls back to chunked REST range calls for selected-regimen hydration and gap collection on plans where crypto minute flat files are not available |

## Bounded Model Surfaces

- `spot_chain_macro_v1`
  - minute-by-mint feature lane from canonical spot, market-structure, chain, and macro truth
- `global_regime_inputs_15m_v1`
  - market-wide 15-minute feature lane built from Coinbase **spot** proxy products plus captured-at-safe macro context
  - Coinbase futures/perps and non-crypto contracts are ingested as context-only evidence for later use and do not currently widen the runtime feature owner
- `global_regime_v1`
  - bounded regime scorer with a four-state Gaussian HMM when `hmmlearn` is installed and a Gaussian-mixture fallback when it is not
- `intraday_meta_stack_v1`
  - shadow-only evaluation lane with walk-forward regime history, ATR-style triple-barrier labels, `IsolationForest`, `RandomForest`, `XGBoost`, optional Chronos-2 summaries, Monte Carlo summaries, and Fibonacci annotations as research-only evidence
- `run-live-regime-cycle`
  - bounded live intraday training lane that captures Jupiter, Helius, and
    Coinbase data, rematerializes canonical feature truth, reruns
    `global_regime_v1`, reruns `regime-model-compare-v1`, evaluates policy and
    risk, and emits a paper-ready receipt
  - keeps execution explicit by requiring a separate `d5 run-paper-cycle ...`
    invocation instead of auto-running paper settlement
- `run-paper-practice-loop`
  - autonomous paper-only operator loop layered on top of the live regime cycle
  - may auto-open and auto-close one bounded `SOL/USDC` paper session at a time
  - adapts only through the SQL-backed paper-practice profile overlay
  - writes JSON/QMD receipts instead of mutating YAML policy, risk code, or
    live execution authority
- `experiment_realized_feedback_v1`
  - advisory comparison receipts that align replayed shadow context to settlement-owned paper fills and latest session snapshots without promoting research outputs into runtime authority

Runtime-adjacent model helpers live under `src/d5_trading_engine/models/`, while shadow-only registries remain explicitly advisory.

The persistent training surface now lives under `training/`, where the repo keeps
vendored autoresearch references, `codex --exec --json`-friendly watcher adapters,
source-set configs, rubrics, and bounded prompt templates. SQL remains
canonical truth, Parquet remains the deep-history warehouse, and QMD remains
the evidence surface those training wrappers point back to.

The control plane is intentionally hybrid:

- `training/automation/bin/training_supervisor.py` handles long-running
  hydration, quickstart/full training-regimen bootstrap, incremental
  collection, review, and one-iteration paper loops from tmux
- repo-local `.codex/` config + hooks stabilize the named persistent `trader`
  lane and the fresh `task` lane
- `codex exec --json -C <repo>` handles fresh bounded semantic work such as
  feature review and repair prompts
- `codex exec resume <SESSION_ID> --json` handles persistent trader review
  continuity for paper sessions, experiments, and condition runs
- `exec-server` / app-server remains a future-phase option after the event and
  receipt contracts stabilize

See [docs/project/trader_cli_crosswalk.md](docs/project/trader_cli_crosswalk.md)
for the truthful command map, source/venue matrix, and the north-star grammar
that the repo is intentionally not pretending to implement yet.

These surfaces remain non-promoting at runtime. The truthful claim is that the repo now has deterministic features, a bounded regime score, explicit policy eligibility traces, one hard risk gate, one bounded execution-intent owner, one quote-backed paper settlement owner, one settlement-owned spot-first backtest replay ledger, one bounded shadow evaluation lane, one bounded canonical label-program loop, one bounded strategy challenger loop, and advisory realized-feedback comparison receipts grounded in settlement truth; it does not yet have runtime model promotion, fully accepted canonical label truth, fully accepted strategy-family governance, or derivative widening.

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
