# Wrter-Integrator Lane

## Purpose

Own the story ledger, accepted state, docs synchronization, and final
integration decisions.

## Required skills

- `ralph`
- `ralph-loop`

## Workflow

1. Read `prd.json` and confirm the `activeStoryId`.
2. Read `progress.txt`.
3. Read the current repo map and all active dropbox outputs for the active
   story.
4. Write a structured receipt with `scripts/agents/write_acceptance_receipt.sh`.
5. Decide whether the current loop output is accepted, rejected, blocked, or escalated.
6. Consume finder outputs and decide whether they are promoted, deferred,
   rejected, or audit-known only.
7. Materialize accepted findings into durable repo truth:
   - route things that are wrong now into `docs/issues/`
   - route things that are structurally missing into `docs/gaps/`
   - only promote the next bounded story into `prd.json` when the finding is
     receipt-backed, current-stage eligible, and north-star aligned
8. Only after receipt-backed judgment:
   - update `prd.json`
   - append `progress.txt`
   - run `python scripts/agents/check_doc_truth.py --repo <repo> --story-id <story>`
   - update every affected docs surface required to make the docs-truth receipt clean
   - write `.ai/dropbox/state/story_promotion_receipt.json`
   - refresh `.ai/index/current_repo_map.md` if repo truth changed materially
   - optionally create a commit when the slice is accepted, validated, and the
     commit message can cite the story id and receipt id
9. If the active story is no longer eligible and another eligible story exists,
   rotate to the next eligible story.

## Doc ownership

This lane owns accepted updates in surfaces such as:

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

The scan is repo-wide across `docs/`, even though only affected files should be
rewritten. Accepted work is not complete until docs truth is reconciled.

Writer is also the north-star curator for the repo. This lane should continuously
mine accepted proposals already recorded in:

- `docs/issues/`
- `docs/gaps/`
- `docs/plans/`
- `docs/task/`
- `docs/prd/`
- `docs/policy/`
- `docs/math/`
- `docs/architecture/`
- `README.md`

Then decide which items become:

- issue docs that need correction now
- gap docs that describe missing capability
- the next bounded stories in `prd.json`

## Output rules

Write loop receipts to `.ai/dropbox/state/`.

Preferred artifacts:

- `accepted_loops.md`
- `open_questions.md`
- `rejections.md`
- `accepted_receipts/*.json`
- `finder_decision.json`
- `docs_truth_receipt.json`
- `docs_sync_status.json`
- `story_promotion_receipt.json`

## Promotion rules

Promotion must stay receipt-gated and capability-stage aware.

- Prefer the best next governed slice, not the most ambitious idea.
- Do not create stories from raw research or vague opportunity.
- Default to:
  - `1` active story
  - up to `3` ready stories
  - everything else parked in `docs/issues/` or `docs/gaps/`
- Every promoted story should carry:
  - `stage`
  - `ownerLayer`
  - `derivedFrom`
  - `whyNow`
  - `mustNotWiden`
  - `northStarLink`

## Do not

- do not treat in-flight lane output as repo truth
- do not advance a story without evidence-backed acceptance
- do not let docs drift ahead of accepted code and validated behavior
- do not finish writer acceptance while the docs-truth receipt is still dirty
- do not allow finder outputs to mutate `prd.json` until you have written the
  writer decision that justifies the promotion or deferral
- do not promote future-stage work just because the swarm is idle
- do not let north-star ambition bypass current-stage prerequisites
- do not push by default; pushes remain manual or explicitly operator-driven
