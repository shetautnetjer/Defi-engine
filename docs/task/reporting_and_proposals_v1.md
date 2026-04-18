# Reporting And Proposals v1

## Goal

Make QMD evidence, SQL artifact receipts, and proposal truth first-class repo
surfaces after capture runs, paper cycles, and experiment runs.

## Required Outcomes

- every capture run writes `config.json`, `capture_summary.json`, and `report.qmd`
- every paper cycle writes `cycle_summary.json`, `report.qmd`, `proposal.json`,
  and `proposal.qmd`
- every experiment run writes its report packet plus advisory proposal packet
- the new `regime_model_compare_v1` experiment lane writes comparison evidence
  plus an advisory-only `regime_model_compare_follow_on` proposal packet
- `artifact_reference` is the canonical SQL receipt for every written artifact
- `improvement_proposal_v1` is the canonical SQL receipt for every advisory
  proposal
- `proposal_review_v1` is the canonical SQL receipt for every bounded advisory
  review decision
- `proposal_comparison_v1` is the canonical SQL receipt for every bounded
  proposal comparison run
- `proposal_comparison_item_v1` is the canonical SQL receipt for every ranked
  candidate inside a comparison run
- `proposal_supersession_v1` is the canonical SQL receipt for append-only
  same-kind supersession history
- no label, strategy, or paper loop silently mutates `prd.json`,
  `progress.txt`, policy, risk, or runtime eligibility

## Current Scope

- centralized rendering helpers under `src/d5_trading_engine/reporting/`
- QMD templates for capture, experiment, paper, proposal, and proposal-review
  packets
- artifact helpers that compute `content_sha256` and persist `artifact_reference`
- proposal helpers that persist `improvement_proposal_v1`
- deterministic proposal review flow under
  `src/d5_trading_engine/research_loop/proposal_review.py`
- `d5 review-proposal <proposal_id>` for bounded AI-reviewed next-test decisions
- latest review receipt at `.ai/dropbox/state/research_proposal_review_receipt.json`
- deterministic proposal comparison flow under
  `src/d5_trading_engine/research_loop/proposal_comparison.py`
- `d5 compare-proposals` for bounded priority selection and same-kind
  supersession history
- latest priority receipt at
  `.ai/dropbox/state/research_proposal_priority_receipt.json`

## Out of Scope

- live trading authority
- automatic runtime promotion
- policy or risk mutation from advisory research
- human-invisible strategy activation
- `regime_model_compare_follow_on` mutating `prd.json`, `progress.txt`,
  policy, risk, execution, settlement, or runtime config

## Validation

- focused pytest on reporting, proposal, CLI, label, strategy, and paper-cycle flows
- confirm proposal artifacts exist on disk
- confirm review artifacts exist on disk
- confirm comparison artifacts exist on disk
- confirm SQL rows exist in `artifact_reference`, `improvement_proposal_v1`,
  `proposal_review_v1`, `proposal_comparison_v1`,
  `proposal_comparison_item_v1`, and `proposal_supersession_v1`
- confirm QMD packets remain durable evidence alongside JSON payloads
