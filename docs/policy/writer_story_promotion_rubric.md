# Writer Story Promotion Rubric

This policy defines how `writer-integrator` continuously curates repo truth and
promotes the next bounded stories toward the north-star mission.

## Purpose

Writer is not an unbounded idea generator.

Writer is the governed curator that:

- keeps the accepted docs surface current
- records contradictions and missing capability as durable repo truth
- updates `prd.json` and `progress.txt`
- promotes only the best next bounded, receipt-backed work outside the bounded
  research proposal-review loop

This means writer should always prefer the best next governed slice rather than
the loudest or newest idea.

The goal is continuous north-star descent, not continuous activity.

## North-Star Rule

Defi-engine moves toward:

- a paper-first, Solana-first crypto backtesting and paper-trading platform
- regime-aware `up` / `down` / `flat` and broader condition classification
- explicit strategy eligibility
- explicit paper settlement
- later governed widening into Jupiter perps and Coinbase futures

Writer should always prefer the next bounded slice that makes this mission more
truthful, auditable, and stage-ready.

## Required Inputs

Before promoting or parking work, writer should read:

- `docs/issues/governed_product_descent_capability_ladder.md`
- `docs/project/current_runtime_truth.md`
- `docs/prd/crypto_backtesting_mission.md`
- `docs/plans/strategy_descent_and_instrument_scope.md`
- `docs/policy/runtime_authority_and_promotion_ladder.md`
- `prd.json`
- `progress.txt`
- accepted receipts
- docs-truth receipts
- completion-audit receipts
- governed performance receipts
- current proposals already recorded in `docs/issues/`, `docs/gaps/`,
  `docs/plans/`, `docs/task/`, `docs/prd/`, `docs/policy/`, `docs/math/`,
  `docs/architecture/`, and `README.md`

## Routing Rules

Route findings mechanically.

- If it is wrong now, update `docs/issues/`.
- If it is structurally missing, update `docs/gaps/`.
- If it is bounded, current-stage eligible, receipt-backed, and implementation
  relevant, promote it into `prd.json`.
- If it belongs to a future stage, park it in `docs/gaps/` with prerequisites
  instead of promoting it now.

## Promotion Inputs

Receipt-backed findings should normalize into fields such as:

- `contradictions_found`
- `unresolved_risks`
- `missing_capabilities`
- `promotion_targets`
- `next_action`
- `owner_layer`
- `stage`
- `must_not_widen`
- `derived_from_receipt_ids`

Raw research output by itself is not enough to promote a story.

The one narrow exception is bounded research proposal review for:

- `label_program`
- `strategy_eval`
- `regime_model_compare`

Those loops may recommend the next research-stage story only when the machine
law, metrics registry, `improvement_proposal_v1`, `proposal_review_v1`, and the
latest proposal-review receipt all agree that the result is still advisory and
still inside the `LABEL-001` / `STRAT-001` ladder.

`regime_model_compare_follow_on` findings may also queue the next bounded
experiment or backlog note, but they may not be treated as runtime promotion or
as authority to edit policy, risk, execution, or settlement behavior.

## Stage-Aware Prioritization

Highest priority:

- current-truth contradictions
- stale or missing docs that misdescribe landed behavior
- runtime/governance bugs that block truthful acceptance
- missing owner work required before widening

Medium priority:

- backtest-truth and labeling work that unlocks future strategy comparison
- strategy-evaluation and challenger scaffolding
- subtraction work that reduces architecture drift

Lower priority:

- speculative future-stage modeling ideas
- widening to perps or futures before prerequisites are clean
- open-ended research with no bounded owner or acceptance contract

## Story Metadata

Every promoted story should include:

- `stage`
- `ownerLayer`
- `derivedFrom`
- `whyNow`
- `mustNotWiden`
- `northStarLink`

These fields make the story's stage position and promotion rationale explicit.

## Queue Discipline

Default backlog discipline:

- `1` active story
- up to `3` ready stories
- everything else parked in `docs/issues/` or `docs/gaps/`

Do not create new stories just to keep the swarm busy.

## Full Docs Surface

Writer should keep the accepted docs surface current across:

- `docs/sdd/`
- `docs/plans/`
- `docs/task/`
- `docs/runbooks/`
- `docs/prd/`
- `docs/policy/`
- `docs/math/`
- `docs/architecture/`
- `docs/issues/`
- `docs/gaps/`
- `docs/project/`
- `docs/handoff/`
- `docs/README.md`
- `README.md`

The scan is repo-wide. Only affected files should be rewritten.

## Required Artifacts

Each accepted writer pass should leave behind:

- an acceptance receipt
- a docs-truth receipt
- a story-promotion receipt
- updated `prd.json`
- updated `progress.txt`
- updated issue/gap docs as needed

## Hard Stops

Writer must not:

- promote runtime-authority changes from raw research or vague opportunity
- widen scope because the swarm is idle
- bypass current-stage prerequisites
- let docs drift after accepted code changes
- treat unresolved contradictions as \"good enough\"
