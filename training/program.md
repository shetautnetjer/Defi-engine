# Governed Training Program

This file is the repo-owned operating contract for the training lane. It adapts
the stronger program framing from the companion Notion page into the actual D5
runtime, CLI, SQL, and QMD surfaces that already exist in this repo.

The trading-specific execution doctrine lives in `training/trading_agent_harness.md`.
Use that file as the event-by-event harness contract, and use this file as the
broader governed program law.

## Goal

Optimize for the best evidence-driven trading system, not the best free-form
LLM trader. Training exists to propose, test, review, and either keep, revert,
or shadow one bounded change at a time.

## Program Law

- SQL is canonical truth.
- QMD is required evidence.
- `.ai/` is the live control plane, not a second training database.
- `training/` owns prompts, rubrics, wrappers, automation adapters, and program doctrine.
- Paper trading remains the default until scope is explicitly widened through the governed promotion ladder.
- No secret printing, hidden runtime promotion, or direct use of raw private-key material.
- No silent mutation of policy YAML, risk code, or canonical strategy registry.
- Candidate overlays may test labels, features, policy, risk, and source-transform variants in research, shadow, or paper lanes; they do not become authority until promoted.
- Jupiter micro-live execution may only run after readiness gates pass, an explicit expiring arm state exists, and an external signer is configured.
- No broad self-editing loop; all accepted adaptation must pass proposal, comparison, evidence, and promotion controls.

## Event Triggers

Training automation may wake up on events such as:

- `feature_run_completed`
- `condition_run_completed`
- `paper_session_closed`
- `experiment_completed`
- `tests_failed`
- `docs_truth_contract_failed`
- `capture_job_failed`
- `manual_research_request`

If an event payload exists, narrow scope to that event before choosing work.

## Allowed Surfaces

Prefer the repo-owned CLI instead of ad hoc shell choreography:

- `d5 training bootstrap`
- `d5 training hydrate-history`
- `d5 training collect`
- `d5 training walk-forward`
- `d5 training review`
- `d5 training loop`
- `d5 training status`
- `d5 training evidence-gap`
- bounded `d5 capture`, `materialize-features`, `score-conditions`, `run-shadow`, `run-live-regime-cycle`, and `run-paper-cycle` subcommands when the training wrapper calls for them

If the CLI is missing a needed surface, propose or add the smallest missing wrapper instead of inventing a second workflow.

## Default Budget

Unless a task says otherwise:

- max wall-clock per bounded iteration: 30 minutes
- max files changed: 8
- max candidate runs per comparison: 1 baseline plus 1 candidate
- max new dependencies: 0 unless explicitly justified
- max new CLI surfaces: 1

If a task needs more, stop and write a proposal instead of widening scope mid-run.

## Baseline Requirements

Before changing behavior, identify:

- latest comparable SQL metrics
- latest comparable QMD report
- current active paper-practice profile revision
- current feature, condition, and experiment family versions relevant to the target
- the immediate previous accepted baseline for that surface

If no baseline exists, create one first.

## Evidence Ranking

When proposals compete, rank evidence in this order:

1. paper-cycle evidence
2. walk-forward or backtest evidence
3. strategy-eval evidence
4. condition or regime evidence
5. feature-only evidence

Break ties with stability across windows, implementation simplicity, and rollback safety.

## Failure Attribution

Every review packet should classify the primary failure surface:

- data or truth failure
- feature failure
- condition model failure
- regime semantic mapping failure
- strategy-policy failure
- risk failure
- execution or fill-model failure
- settlement or evaluation failure
- automation or governance failure

`d5 training evidence-gap` should be the fast machine-readable version of this
classification. It ranks multiple failure families, records the selected
experiment batch type, requires a falsification candidate, and leaves promotion
to the governed review/comparison ladder.

`d5 diagnose training-window`, `d5 diagnose gate-funnel`, and
`d5 diagnose no-trades` should be the fast runtime-funnel version of the same
discipline. They must explain whether the system failed at data coverage,
feature materialization, condition validity, strategy candidate generation,
policy eligibility, risk approval, quote/fill availability, or settlement.

Change the weakest surface, not the whole system.

## Required Outputs

Every nontrivial training run should leave:

- SQL metrics or ledger rows
- JSON artifacts
- a QMD report or QMD-ready markdown
- artifact references
- the next bounded proposal or the explicit keep, revert, or shadow decision

The packet should record:

- run tag
- targeted surface
- baseline
- keep, revert, or shadow rule
- files touched
- commands run
- observed results
- accepted or rejected decision
- next seam
