# Bootstrap Inventory

Current snapshot of `Defi-engine` after the first source-owner, condition,
policy, risk, execution-intent, settlement, and backtest-truth descent slices
through 2026-04-17.

The capture, condition, policy, risk, execution-intent, settlement, and shadow
surfaces are now real repo truth with point-in-time-safe regime history and
captured-at-safe macro timing. They remain bounded and non-promoting even
though `research_loop/` now has advisory realized-feedback comparison.

The repo now also carries a north-star packet for the longer descent into a
Solana-first backtesting and paper-trading platform. That packet is planning
truth, not proof that the later-stage product is already implemented.

The repo also now carries a policy-only machine-readable swarm packet under
`.ai/swarm/` so packet rules, lane authority, and promotion doctrine do not
live only in prose.

Stage 1 of the governed product-descent ladder is now **current truth
consolidation**. That means accepted work is not finished until code truth,
docs truth, `prd.json`, and `progress.txt` all agree, with `writer-integrator`
owning the continuous docs-sync closeout.

## Public Surface

- Python distribution metadata: `d5engine`
- Import path: `d5_trading_engine`
- Operator CLI: `d5`
- Runtime data paths:
  - SQLite truth DB: `data/db/d5.db`
  - DuckDB mirror: `data/db/d5_analytics.duckdb`
  - Coinbase raw DB: `data/db/coinbase_raw.db`
  - Raw landing zone: `data/raw/{provider}/{YYYY-MM-DD}/`

## Inventory

| Area | State | Notes |
|------|-------|-------|
| Project metadata | implemented | `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`, `alembic.ini` are present |
| Config/common | implemented | settings now include the mint-locked universe, Jupiter throttle, Coinbase raw DB path, and UTC event-time helpers |
| SQLite truth layer | implemented | SQLAlchemy engine + ORM models + Alembic migrations exist |
| DB bootstrap path | implemented | `d5 init` runs Alembic migrations to head |
| Raw storage | partial | JSONL writing is implemented; Parquet directories exist but Parquet export is not written yet |
| DuckDB mirror | implemented | SQLite attach/copy flow exists in `storage/analytics/duckdb_mirror.py` |
| Jupiter adapter/normalizer | implemented | spot token list, prices, and two-sided quotes with capture metadata are present |
| Helius adapter | partial | enhanced transaction REST, tracked-address discovery, and hardened raw websocket capture with reconnect / heartbeat exist |
| Helius normalizer | partial | address/program registry population and `solana_transfer_event` exist; deeper program decoding is still deferred |
| Coinbase adapter/normalizer | partial | public products, candles, trade prints, and L2 book capture exist; execution and fill modeling are deferred |
| Massive adapter/normalizer | partial | first-pass reference, snapshot, and historical minute-aggregate paths now normalize into canonical truth; wider entitlement coverage remains deferred |
| Capture runner | implemented | ingest run bookkeeping, raw write, normalization, and health logging are wired across Jupiter, Helius, Coinbase, FRED, and Massive |
| Capture lane status owner | implemented | `capture/lane_status.py` now owns the governed lane manifest, freshness-state derivation, readiness-only handling, and required-blocker reporting |
| CLI | implemented | current commands are `init`, `capture`, `materialize-features`, `score-conditions`, `run-shadow`, `status`, and `sync-duckdb`; `d5 status` now includes a per-lane capture-freshness section |
| Condition/policy/risk/execution-intent/settlement/backtest | partial | `condition/` now owns `global_regime_v1`, `policy/` now owns the first explicit `global_regime_v1` eligibility traces, `risk/` now owns the first explicit `global_regime_v1` veto receipts, `execution_intent/` now owns the first bounded paper-only `execution_intent_v1` selector, and `settlement/` now owns both the explicit quote-backed paper session / fill / position / report ledger and the first spot-first backtest replay ledger |
| Features | partial | `spot_chain_macro_v1` and `global_regime_inputs_15m_v1` now materialize freshness-gated feature tables plus `feature_materialization_run` receipts |
| Models/research_loop/trajectory | partial | `research_loop/` now owns one bounded PIT-safe shadow experiment lane plus advisory realized-feedback comparison receipts over settlement truth, but it remains research-only; `trajectory/` remains mostly scaffolded |
| Orchestration | implemented | repo-local Ralph/tmux swarm pack now exists under `.ai/`, `prd.json`, `progress.txt`, `scripts/ralph/`, and `scripts/agents/` for story-driven multi-lane execution with lane-health supervision |
| Tests | implemented | default `pytest` stays offline-safe; live-gated Jupiter and Helius integration harnesses exist for provider receipts |
| Docs | partial | docs inventory, architecture, runbook, validation notes, active task docs, and north-star mission/scope/math/governance docs exist |

## Current Drifts From The Earlier Bootstrap Sketch

- the current CLI is generic (`d5 capture <provider>`) rather than provider-specific top-level commands
- the CLI lives in `src/d5_trading_engine/cli.py`, not `src/d5_trading_engine/cli/main.py`
- the current implementation still uses concentrated single-file owners like `condition/scorer.py`, `risk/gate.py`, and `settlement/paper.py`
- README and docs must continue to treat current code as truth until deeper research and runtime layers are actually implemented

## Repo-Local Orchestration

- `.ai/agents/` owns lane guidance for the research, builder, architecture, and writer-integrator roles
- `.ai/index/current_repo_map.md` is the fast current-truth index for the swarm
- `.ai/swarm/` holds policy-only machine-readable swarm law for packet reads,
  lane authority, and promotion doctrine
- `docs/issues/governed_product_descent_capability_ladder.md` is the durable
  long-horizon issue guide for future assistants and backlog promotion
- `docs/gaps/` now decomposes the next missing capability layers into explicit
  gap surfaces rather than leaving them only in chat or one broad blocker file
- `.ai/dropbox/` is working exchange only, not canonical repo truth
- `.ai/dropbox/state/` now produces runtime lane-health, compacted mailbox, finder, runtime, acceptance, and detached-supervisor receipts for continuous supervision
- `prd.json` and `progress.txt` are the canonical story ledger for long-horizon Ralph loops and now carry explicit story states plus top-level swarm completion truth (`swarmState`, `completionAuditState`)
- the writer-integrator lane is the only lane allowed to advance story state or convert accepted work into repo docs truth
- tmux startup and detached supervision are now intentionally separate lifecycle commands
- the 4-lane swarm remains fixed; architecture-finder and research-finder are mode switches inside the existing lanes rather than new permanent panes
