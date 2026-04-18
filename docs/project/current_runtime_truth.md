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
