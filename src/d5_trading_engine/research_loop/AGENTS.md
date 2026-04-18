# `research_loop/` Navigation

This package is advisory-only.

It owns:

- experiment comparison
- realized feedback
- shadow evaluation
- bounded improvement proposals
- deterministic proposal review
- proposal comparison and supersession

It does **not** own runtime authority.

Rules for this folder:

- do not mutate policy, risk, execution, settlement, `prd.json`, or
  `progress.txt` as part of research review/comparison flows
- write SQL truth, artifact references, JSON artifacts, and QMD evidence
- keep recommendations bounded and reviewable
- fail closed when evidence is weak, missing, or outside governance scope

If a change here starts to widen runtime behavior, stop and push the contract
back to the owning runtime layer instead of freelancing promotion logic.
