# Runtime Authority and Promotion Ladder

This file defines what is allowed to influence runtime behavior and how
research evidence becomes eligible for promotion.

## Authority order

Runtime authority descends through explicit owners:

1. source truth and canonical storage
2. deterministic features
3. bounded condition scoring
4. policy eligibility traces
5. hard risk gating
6. explicit execution intent
7. settlement and realized paper truth
8. gated micro-live execution after explicit promotion and arming

Anything outside that chain is advisory until promoted.

## Advisory surfaces

These are advisory by default:

- shadow model outputs
- external research findings
- memory systems
- finder audits
- autoresearch hypotheses
- Chronos-2 summaries
- Monte Carlo studies
- Fibonacci annotations
- ANN or relationship experiments

Advisory surfaces may critique, compare, or propose. They may not silently
control strategy eligibility, risk, execution, or settlement.

## Promotion ladder

An advisory surface becomes a promotion candidate only when it has:

- an explicit contract
- deterministic inputs
- replayable validation
- documented failure modes
- risk compatibility
- bounded scope
- receipt-backed writer acceptance

Promotion must also state:

- what owner layer receives it
- what old behavior it replaces, if anything
- what rollback path exists

## Continuous learning ladder

The adaptive research system may evolve trading behavior only through versioned
candidate overlays:

- label-program overlays
- feature toggles or materializer overlays
- condition and regime-threshold overlays
- strategy-policy compatibility overlays
- risk-threshold or veto-sensitivity overlays
- source-normalization overlays

Candidate overlays are research, shadow, or paper evidence until a promotion
decision accepts them. They may not directly mutate authoritative runtime files
or bypass the risk gate.

## Micro-live gate

Jupiter micro-live is allowed only after all of the following are true:

- rolling paper win rate is at least 80%
- at least 20 settled paper trades exist in the evaluated window
- at least 1 settled trade per week is sustained for 4 consecutive weeks
- net expectancy after fees and slippage is positive
- profit factor is at least 1.5
- drawdown remains within the configured micro-live cap
- quote and fill-health checks are clean
- unexplained decision gaps are zero
- at least one candidate comparison is accepted
- an operator writes an explicit expiring arm state
- signing is delegated to an external signer or wallet command

The engine must not read, store, print, or derive raw Solana private-key
material. Micro-live receipts may include signatures, request IDs, mints,
amounts, and public keys, but not private keys or seed material.

The initial micro-live ladder is:

1. `research`
2. `shadow`
3. `paper`
4. `micro_live`
5. `scaled_live`

Automation may auto-promote only into bounded paper-runtime candidates. Promotion
from paper to `micro_live` requires passing gates and explicit operator arming.

## Writer-integrator authority

Writer-integrator remains the only lane allowed to:

- accept or reject runtime-authority promotion candidates
- update accepted repo truth across the docs packet
- append `progress.txt` for accepted runtime and governance slices
- convert audit findings into canonical backlog truth outside the bounded
  bounded research proposal review loop
- treat a research result as a governed runtime or non-research follow-on story

Builder, research, and architecture lanes may propose. They do not promote
runtime authority.

## Bounded Research Proposal Review

The repo now allows one narrow automation exception so `LABEL-*` and `STRAT-*`
loops can keep running without per-run human gating.

This bounded research proposal review loop is intentionally scoped to advisory
research stories only.

Automation may review the next advisory story candidate only when all of the
following are true:

- the source story is in `stage: regime_and_label_truth` or
  `stage: strategy_research`
- the story class is `label_program`, `strategy_eval`, or
  `regime_model_compare`
- the result is still advisory
- the loop writes durable proposal truth in `improvement_proposal_v1`
- the loop writes durable review truth in `proposal_review_v1`
- `d5 review-proposal <proposal_id>` writes `review.json`, `review.qmd`, and
  `research_proposal_review_receipt.json`
- the next story stays inside the same bounded research ladder

Automation may not promote:

- policy authority
- risk authority
- execution intent
- settlement authority
- instrument expansion
- any other runtime-authority surface

This keeps the AI-reviewed research loop fast while leaving runtime ownership
under explicit governance.

Review decisions remain advisory even when they are `reviewed_accept`.

- they may approve the next bounded research test
- they may not widen policy, risk, execution, settlement, or runtime authority
- they may not edit `prd.json`, `progress.txt`, or runtime config as part of
  the review itself

## Bounded Proposal Comparison and Priority Selection

The repo also allows bounded comparison of already-reviewed advisory proposals.

This comparison layer is governance truth, not runtime authority.

- `proposal_comparison_v1` stores the comparison run
- `proposal_comparison_item_v1` stores ranked candidates and evidence
  breakdowns
- `proposal_supersession_v1` stores append-only same-kind supersession edges
- `d5 compare-proposals` writes `comparison.json`, `comparison.qmd`, and
  `research_proposal_priority_receipt.json`

Comparison may:

- rank reviewed proposals across regime and condition slices
- choose one bounded next experiment with `selected_next`
- mark lower-ranked same-kind competitors as `superseded`
- include `regime_model_compare_follow_on` only while it remains advisory-only

Comparison may not:

- widen policy, risk, execution, settlement, or runtime authority
- auto-review missing proposal packets
- edit `prd.json`, `progress.txt`, or runtime config

## Commit governance

Git history should reflect receipt-backed truth:

- builder does not auto-commit
- writer-integrator may create commits for accepted slices
- pushes stay manual or explicitly operator-driven by default
- accepted commits should reference story id, receipt id, and validation

## Default safe action

When evidence is weak or promotion criteria are incomplete:

- no trade
- no promotion
- no silent widening
- keep the result advisory
