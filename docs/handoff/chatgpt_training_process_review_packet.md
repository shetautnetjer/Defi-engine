# ChatGPT Pro Review Packet: Training and Paper Experiment Loop

Created: 2026-04-20
Repo: `https://github.com/shetautnetjer/Defi-engine`
Current anchor commit: `d2cb67f Add replay audit artifacts for paper backtests`

## Review Intent

Use this packet as an external design-review prompt for the D5 paper-first trading and research engine. The goal is not generic trading advice. The goal is a small, testable architecture improvement plan for continuous paper training, replay-audit-driven experiments, and safer profile/governor learning.

Hard constraints:

- Paper trading only.
- Do not propose live trading or live order routing.
- Do not weaken risk gates.
- Keep runtime strategy policy, risk policy, research profiles, and automation supervision separate.
- Treat profiles as soft research priors, not runtime authority.
- Treat SQL, code, schemas, configs, and tests as repo truth.

## Primary Questions

1. What is the cleanest design for continuous paper training without hidden live authority?
2. How should the system distinguish "automation watcher is alive" from "paper-practice trading loop is actively running"?
3. What status fields should expose loop health, replay health, experiment health, and restart recommendations?
4. How should replay audit CSV/Parquet feed experiment generation and profile-governor scoring?
5. How should the system handle a strategy/runtime mismatch like a flat strategy selected while the runtime currently supports long-only paper entries?
6. What is the minimum useful experiment lifecycle: proposal, replay, scorecard, decision, receipt?
7. How do we keep profiles as soft research priors without overfitting or turning them into runtime policy?
8. What should be tested first so the system is safer and easier to operate?

## Files To Review First

These files are tracked in Git and should be available from the repo at the anchor commit or later:

- `AGENTS.md`
- `README.md`
- `training/README.md`
- `training/trading_agent_harness.md`
- `training/program.md`
- `src/d5_trading_engine/cli.py`
- `src/d5_trading_engine/paper_runtime/practice.py`
- `src/d5_trading_engine/research_loop/training_runtime.py`
- `training/automation/bin/training_supervisor.py`
- `training/automation/bin/codex_event_watcher.py`
- `training/automation/config/automation_rules.json`
- `.ai/profiles.toml`
- `.ai/policies/profile_router_policy.v1.json`
- `.ai/schemas/profile.schema.json`
- `.ai/schemas/profile_governor_decision.schema.json`
- `.ai/schemas/profile_router_policy.schema.json`
- `.ai/schemas/meta_governor_scorecard.schema.json`

Review these supporting registries if the suggested design touches strategy families, metrics, or swarm/agent routing:

- `.ai/swarm/strategy_registry.yaml`
- `.ai/swarm/metrics_registry.yaml`
- `.ai/swarm/promotion_ladder.yaml`
- `docs/math/strategy_family_registry.md`
- `docs/project/repo_reality_2026-04-20.md`

## Current Evidence Snapshot

Historical data readiness:

- Latest `d5 training status --json` reported `729` available warehouse-backed days out of a requested `730`.
- Training profile `quickstart_300d` is ready.
- Strongest available profile `full_730d` is also reported ready.
- The missing day does not block 300-day or 730-day readiness in the current status output.

Latest 300-day walk-forward run:

- Run id: `backtest_walk_forward_afbdb062864a`
- Training profile: `quickstart_300d`
- History window: `2025-06-25..2026-04-20`
- Replay window: `2026-01-21..2026-04-20`
- Replay rows: `8545`
- Ending paper cash: `100.0`
- Realized PnL: `0.0`
- Close moved from `127.63` to `83.54`, or `-34.545%`

Replay audit artifacts:

- `data/research/paper_practice/backtests/backtest_walk_forward_afbdb062864a/summary.json`
- `data/research/paper_practice/backtests/backtest_walk_forward_afbdb062864a/window_01.json`
- `data/research/paper_practice/backtests/backtest_walk_forward_afbdb062864a/window_01_replay_audit_summary.json`
- `data/research/paper_practice/backtests/backtest_walk_forward_afbdb062864a/window_01_replay_audit.csv`
- `data/research/paper_practice/backtests/backtest_walk_forward_afbdb062864a/window_01_replay_audit.parquet`

Important audit finding:

- The market was not flat.
- Direction counts were `up=4318`, `down=4227`.
- Semantic regime counts were `long_friendly=4338`, `no_trade=2895`, `short_friendly=955`, `risk_off=357`.
- The selected top strategy family was `flat_regime_stand_aside_v1`.
- The strategy target label was `flat`.
- Runtime-long-supported count was `0`.
- Would-open-runtime-long count was `0`.
- Dominant blocker was `strategy_target_not_runtime_long:flat=8545`.

Interpretation:

The zero-trade result is not evidence that the market was flat. It is evidence that the strategy selection and the current paper runtime entry model are mismatched. The current runtime only models long paper entries, while the selected strategy family is a flat stand-aside family allowed in `no_trade` and `risk_off` regimes.

## Experiment Inventory So Far

The repo has produced more than one experiment type, but the outputs are not yet unified into a strong experiment engine:

- `61` regime-model comparison proposal runs under `data/research/regime_model_compare/`.
- `1` strategy challenger report under `data/research/strategy_eval_runs/`.
- `50` paper-practice decision folders under `data/research/paper_practice/decisions/`.
- `52` live-regime proposal cycles under `data/research/live_regime_cycle/`.
- `52` completed training-review summaries under `data/research/training/reviews/`.
- Multiple source-collection reports under `data/research/source_collection/`.

The most important weakness:

These artifacts exist, but they are still more like scattered receipts than a unified learning loop. The current paper-practice stream has been repetitive: many recent decisions are `no_trade` with reason codes like `strategy_target_not_runtime_long:flat` and `strategy_regime_not_allowed:long_friendly`.

## What Needs Design Help

The next implementation should probably focus on a status-first, experiment-engine-first slice:

1. Add explicit training health or doctor output.
2. Separate automation health from paper-loop health.
3. Expose whether the latest paper loop is terminal, stale, actively running, or restart-recommended.
4. Convert replay audit summaries into experiment inputs.
5. Add a minimal experiment lifecycle contract.
6. Add a profile-neutral validation gate before any profile-found edge is trusted.
7. Keep strategy and risk policy independent from profile preferences.

Suggested minimal status fields:

- `historical_data_ready`
- `selected_training_regimen`
- `available_history_days`
- `automation_watcher_status`
- `paper_loop_desired_mode`
- `paper_loop_actual_status`
- `paper_loop_latest_run_id`
- `paper_loop_latest_terminal_status`
- `paper_loop_process_present`
- `paper_loop_stale`
- `restart_recommended`
- `restart_reason_codes`
- `latest_replay_audit_path`
- `latest_replay_audit_summary`

Suggested minimal experiment lifecycle:

- `experiment_proposal`
- `replay_audit`
- `scorecard`
- `profile_governor_review`
- `decision`
- `receipt`

## Ask For Concrete Output

Please provide:

1. A small v1 architecture with exact boundaries between automation watcher, training runtime, paper practice loop, strategy evaluation, and profile governor.
2. A suggested CLI/status contract.
3. The first 5 tests to add.
4. A safe restart policy for continuous paper loops.
5. A minimal schema for replay-audit-to-experiment conversion.
6. A short list of anti-overfit safeguards.
7. Any files that should be split or renamed to make the training loop easier to reason about.

Avoid:

- Live trading suggestions.
- Leverage or order-routing advice.
- Strategy hardcoding.
- Profile-driven runtime authority.
- Broad rewrites before the status and experiment contracts are clear.
