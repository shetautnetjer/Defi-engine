# Writer-Integrator Lane

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
7. Only after receipt-backed judgment:
    - update `prd.json`
    - append `progress.txt`
    - run `python scripts/agents/check_doc_truth.py --repo <repo> --story-id <story>`
    - update every affected docs surface required to make the docs-truth receipt clean
    - refresh `.ai/index/current_repo_map.md` if repo truth changed materially
   - optionally create a commit when the slice is accepted, validated, and the
     commit message can cite the story id and receipt id
7. If the active story is no longer eligible and another eligible story exists,
   rotate to the next eligible story.

## Doc ownership

This lane owns accepted updates in surfaces such as:

- `docs/plans/`
- `docs/issues/`
- `docs/gaps/`
- `docs/sdd/`
- `docs/project/`
- `docs/handoff/`
- `README.md`

The scan is repo-wide across `docs/`, even though only affected files should be
rewritten. Accepted work is not complete until docs truth is reconciled.

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

## Do not

- do not treat in-flight lane output as repo truth
- do not advance a story without evidence-backed acceptance
- do not let docs drift ahead of accepted code and validated behavior
- do not finish writer acceptance while the docs-truth receipt is still dirty
- do not allow finder outputs to mutate `prd.json` until you have written the
  writer decision that justifies the promotion or deferral
- do not push by default; pushes remain manual or explicitly operator-driven
