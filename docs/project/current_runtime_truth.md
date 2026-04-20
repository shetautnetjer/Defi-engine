# Current Runtime Truth

This file is the compact runtime-truth packet for the Defi-engine swarm.

Read it before widening backlog truth or claiming a runtime owner is still
missing.

Stage 1 of the governed product descent is current-truth consolidation. In
plain terms, the current truth consolidation rule means the repo should prefer
clean contracts, clean docs, and clean acceptance state over widening into new
product surfaces too early.

## Real now

The repo already owns these runtime-adjacent surfaces:

- source truth in canonical SQLite plus provider-backed capture receipts
- explicit capture freshness ownership
- bounded deterministic feature materialization
- bounded condition scoring
- explicit policy tracing
- explicit hard risk gating
- explicit execution intent ownership
- explicit paper settlement and paper reporting
- explicit spot-first backtest replay truth
- bounded shadow evaluation
- advisory realized-feedback comparison between shadow and paper outcomes

Current concrete surfaces include:

- `spot_chain_macro_v1`
- `global_regime_inputs_15m_v1`
- `global_regime_v1`
- `policy_global_regime_trace_v1`
- `risk_global_regime_gate_v1`
- `execution_intent_v1`
- `paper_session`
- `paper_fill`
- `paper_position`
- `paper_session_report`
- `backtest_session_v1`
- `backtest_fill_v1`
- `backtest_position_v1`
- `backtest_session_report_v1`
- `experiment_realized_feedback_v1`
- `intraday_meta_stack_v1`
- `regime_model_compare_v1`
- `live_regime_cycle`

## Next governed gaps

The Stage 1 runtime-owner seam is now closed:

- `execution_intent/` owns explicit paper-only spot intent between `risk/` and
  `settlement/`

The Stage 2 backtesting seam is now also closed:

- `settlement/backtest.py` owns a bounded spot-first replay ledger with
  explicit session, fill, position, and report assumptions

The first paper-runtime app seam is now also real:

- `paper_runtime/` owns a bounded paper-only operator loop that reads advisory
  strategy output, keeps quote selection explicit, calls policy/risk/intent and
  settlement owners, and writes UTC-dated QMD receipts

The next governed product gaps are now:

- canonical regime and label truth
- strategy registry and challenger governance
- real-data paper-trading readiness, including enough governed regime history to
  run paper cycles on live repo truth
- a repeatable historical-to-live Solana paper ladder grounded in the bounded
  Massive free-tier minute window and live Jupiter/Helius/Coinbase receipts
- bounded AI-reviewed research proposal packets between `LABEL-001` and
  `STRAT-001` are now allowed as long as the result stays advisory

The active orchestration hardening work is therefore about:

- keeping the swarm state monotonic and auditable
- keeping the standalone watcher advisory, lock-protected, and subordinate to
  `prd.json` truth
- keeping the entire `docs/` tree aligned with accepted repo truth
- letting writer-integrator finish acceptance cleanly instead of letting stale
  lane liveness pretend to be progress
- letting writer-integrator mine accepted proposals from docs, issues, gaps,
  and receipts so the next bounded stories stay north-star aligned
- promoting `LABEL-001` as the next bounded capability slice after the accepted
  backtest truth layer

## Research-only by default

These remain advisory unless promoted through the runtime authority ladder:

- Chronos-2
- Monte Carlo
- Fibonacci-derived feature families
- autoresearch
- ANN / relationship modeling
- finder audits
- shadow model outputs

They may propose, compare, or critique. They may not silently become runtime
authority.

## Swarm truth rule

Canonical swarm truth still lives in:

- `prd.json`
- `progress.txt`
- accepted docs

Writer-integrator is the only lane allowed to turn accepted findings into:

- updated docs truth across `docs/sdd/`, `docs/plans/`, `docs/task/`,
  `docs/runbooks/`, `docs/prd/`, `docs/policy/`, `docs/math/`,
  `docs/architecture/`, `docs/issues/`, `docs/gaps/`, `docs/project/`, and
  `README.md`
- the next bounded stories in `prd.json`
- durable receipts in `.ai/dropbox/state/`

The `.ai/dropbox/` tree is an exchange surface. The `.ai/swarm/*.yaml` layer is
a machine-readable governance packet, not a live runtime source of truth in v1.

The repo now also carries a standalone watcher contract:

- `.ai/swarm/watcher.yaml`
- `.ai/templates/watcher.md`
- `scripts/agents/codex_watch_adapter.py`

That watcher may review paper-runtime cycles, strategy challenger reports, and
story-promotion receipts, but it stays advisory-only and writes receipts under
`data/reports/watcher/` instead of editing repo-tracked truth.

The one bounded exception is research proposal review:

- `LABEL-*` and `STRAT-*` story classes may advance an advisory proposal-review
  packet automatically
- `improvement_proposal_v1` stores the proposal truth
- `proposal_review_v1` stores the deterministic AI-review decision truth
- `d5 review-proposal <proposal_id>` writes `review.json`, `review.qmd`, and
  `.ai/dropbox/state/research_proposal_review_receipt.json`
- only while the result stays advisory and outside runtime authority
- the review loop may not edit `prd.json`, `progress.txt`, policy, risk,
  strategy eligibility, or runtime config

The next bounded governance seam is proposal comparison and priority selection:

- `proposal_comparison_v1` stores comparison-run truth
- `proposal_comparison_item_v1` stores ranked proposal candidates and score
  breakdowns
- `proposal_supersession_v1` stores append-only same-kind supersession edges
- `d5 compare-proposals` writes `comparison.json`, `comparison.qmd`, and
  `.ai/dropbox/state/research_proposal_priority_receipt.json`
- `selected_next` and `superseded` are governance states for bounded next-test
  choice only
- comparison may choose the next bounded experiment, but it may not edit
  `prd.json`, `progress.txt`, policy, risk, execution, settlement, or runtime
  config

The current shadow research surface now also includes bounded regime-model
comparison:

- `d5 run-shadow regime-model-compare-v1`
- `experiment_run` with `experiment_name = regime_model_compare_v1`
- artifact evidence under `data/research/regime_model_compare/<run_id>/`
- advisory-only `regime_model_compare_follow_on` proposal packets
- no widening of policy, risk, execution, settlement, or runtime authority

The current paper-training surface also includes a bounded live-cycle owner:

- `d5 run-live-regime-cycle`
- bounded live capture order:
  - Jupiter prices
  - Jupiter quotes
  - Helius transactions
  - Coinbase candles for bounded spot/futures/perp context products after
    merging default spot inventory with filtered futures and perpetual product
    discovery
  - Coinbase book when the product exposes a public pricebook
  - Coinbase market trades
- rematerializes:
  - `spot_chain_macro_v1`
  - `global_regime_inputs_15m_v1`
- reruns:
  - `global_regime_v1`
  - `regime_model_compare_v1`
- evaluates:
  - `policy_global_regime_trace_v1`
  - `risk_global_regime_gate_v1`
- writes a paper-ready receipt with the freshest eligible `SOL/USDC` quote
  snapshot and the latest condition/policy/risk ids
- keeps the current regime/materialization path spot-only even though Coinbase
  now also ingests context-only futures, perp, gold, and crude-oil products
- does not auto-run settlement and does not widen runtime authority

The current paper-runtime stack now also includes a bounded autonomous
paper-practice overlay:

- `d5 run-paper-practice-bootstrap`
- `d5 run-paper-practice-loop`
- `d5 paper-practice-status`
- `d5 run-paper-close`
- SQL-backed profile overlay truth in:
  - `paper_practice_profile_v1`
  - `paper_practice_profile_revision_v1`
  - `paper_practice_loop_run_v1`
  - `paper_practice_decision_v1`
- automatic adaptation is limited to paper-only profile keys such as confidence,
  stops, cooldown, and selected strategy family
- no YAML policy mutation, no risk-gate code mutation, and no live execution
  authority widening

The current historical ladder is now bounded, explicit, and evidence-first:

- `d5 capture massive-minute-aggs --full-free-tier`
- uses the repo's Massive free-tier assumption of a 2-year minute-history window
- preserves raw replay artifacts per day as JSONL or CSV.gz source artifacts plus partitioned Parquet for replay reads
- normalizes only `X:SOLUSD`, `X:BTCUSD`, and `X:ETHUSD` into canonical SQL
- feeds the canonical 15-minute regime feature lane rather than a separate
  shadow-only store
- prefers Massive flat files when those entitlements and credentials are available
- falls back to REST minute aggregates for incremental hydration and gap repair on plans where crypto minute flat files are unavailable
- uses bounded Massive REST range calls with `limit=50000` per ticker request so selected-regimen hydration does not make one REST call per day
- now supports cache-first training wrappers:
  - `d5 hydrate-history --training-regimen auto`
  - `d5 training hydrate-history`
  - `d5 training collect`
  - `d5 training status`
- paper-practice bootstrap now supports named training regimens:
  - `auto` = fastest ready regimen from available history, so paper training can start once `quickstart_300d` is satisfied
  - `quickstart_300d` = earlier paper-only bootstrap
  - `full_730d` = heavier long-history path when explicitly selected
- these regimens change data budget and replay shape only; strategy, policy, and risk remain separate owners
- research-bias profiles are a separate layer from training regimens and live in `.ai/profiles.toml` with `.ai/schemas/profile.schema.json`; they shape what to explore, not what runtime policy/risk may execute
- the intended operating model is:
  - finish the selected local historical training-regimen window first
  - continue filling the full historical cache as a separate explicit `full_730d` concern
  - reuse local SQL, raw source artifacts, and Parquet artifacts for walk-forward and review
  - append only missing/new source data afterward
  - avoid repulling already-cached history during continuous training

The incremental source-collection owner is now explicit:

- `capture/source_collection.py`
- `d5 training collect`
- collects the configured missing Massive slice plus fresh Jupiter, optional
  Helius, and Coinbase data
- writes `.ai/dropbox/state/source_collection_status.json`
- stays subordinate to the local historical cache instead of treating provider
  history as something to repull forever

The trading evidence contract is now also explicit:

- trading-facing runs converge on `config.json` + `summary.json` + `report.qmd`
- QMD remains the human-and-LLM evidence packet with small YAML frontmatter
- SQL remains canonical truth and Parquet remains the deep-history warehouse
- see `docs/task/trading_qmd_report_contract.md` for the required reporting sections

The current Codex automation topology is now also explicit:

- repo-local `.codex/config.toml` and `.codex/hooks.json` define trader/task
  automation defaults
- the named persistent `trader` lane owns resumed paper-session, experiment,
  and condition review continuity
- the fresh `task` lane owns one-shot feature review and repair work
- `training/automation/state/lane_sessions.json` stores lane session continuity
- `training/automation/state/watcher_status.json` stores watcher heartbeat and
  trader-lane health for operator-facing status reads
- `training/automation/bin/training_supervisor.py` is the tmux-owned process
  steward for hydration, selected-regimen bootstrap, collection, review, and
  one-iteration paper loops
- app-server and exec-server stay deferred until the current lane/event/receipt
  contracts prove stable

`d5 training status --json` now intentionally separates:

- warehouse completeness: raw + Parquet + normalized SQL
- capture progress: the latest incremental source-collection receipt
- runtime loop truth from SQL versus the latest paper-practice status receipt

If those surfaces disagree, the status payload should expose the conflict
instead of flattening it away.
