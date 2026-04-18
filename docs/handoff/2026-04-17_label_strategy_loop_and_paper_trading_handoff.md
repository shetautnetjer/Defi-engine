# 2026-04-17 Label / Strategy Loop And Paper-Trading Handoff

## Status

This handoff is retained as historical context, but its original automation
details have been superseded by the bounded proposal-review flow now reflected
in repo truth.

Current authoritative references:

- [docs/project/current_runtime_truth.md](../project/current_runtime_truth.md)
- [docs/policy/runtime_authority_and_promotion_ladder.md](../policy/runtime_authority_and_promotion_ladder.md)
- [docs/task/reporting_and_proposals_v1.md](../task/reporting_and_proposals_v1.md)
- [docs/plans/paper_trading_readiness_and_live_gate.md](../plans/paper_trading_readiness_and_live_gate.md)

## What Still Holds

- the repo is paper-first and Solana-first
- canonical truth lives in SQL with replayable raw payloads
- QMD evidence remains required for capture, paper, and experiment flows
- live trading, unattended wallet signing, and risk loosening remain out of
  scope

## What Changed Since The Original Handoff

- advisory proposal packets are stored in `improvement_proposal_v1`
- deterministic AI-reviewed proposal decisions are stored in `proposal_review_v1`
- the latest bounded review receipt lives at
  `.ai/dropbox/state/research_proposal_review_receipt.json`
- review evidence is written under
  `data/research/proposal_reviews/<proposal_id>/<review_id>/`
- no research loop mutates `prd.json`, `progress.txt`, policy, risk, or runtime
  eligibility as part of proposal review

## Current Commands

Use these bounded commands instead of the older research-loop flow:

```bash
d5 materialize-features global-regime-inputs-15m-v1
d5 materialize-features spot-chain-macro-v1
d5 run-label-program canonical-direction-v1
d5 run-strategy-eval governed-challengers-v1
d5 review-proposal <proposal_id>
```

## Current Interpretation

`run-label-program`, `run-strategy-eval`, and bounded paper-cycle flows may
emit advisory proposal packets automatically. They do not self-promote runtime
behavior.

`d5 review-proposal <proposal_id>` may accept, hold, or reject the next
advisory research step, but it remains an evidence and governance surface only.

## Recommended Resume Point

When resuming from this handoff, start from current repo truth instead of the
older implementation notes:

```bash
git status --short
pytest -q tests/test_label_strategy_loop.py tests/test_improvement_proposals.py
d5 materialize-features global-regime-inputs-15m-v1
d5 materialize-features spot-chain-macro-v1
d5 run-label-program canonical-direction-v1
```
