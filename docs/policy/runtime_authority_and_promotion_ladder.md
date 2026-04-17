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

## Writer-integrator authority

Writer-integrator remains the only lane allowed to:

- accept or reject promotion candidates
- update `prd.json`
- append `progress.txt`
- convert audit findings into canonical backlog truth
- treat a research result as a governed follow-on story

Builder, research, and architecture lanes may propose. They do not promote.

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
