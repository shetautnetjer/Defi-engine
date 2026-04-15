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
4. Decide whether the current loop output is accepted or rejected.
5. Only after acceptance:
   - update `prd.json`
   - append `progress.txt`
   - update the relevant docs
   - refresh `.ai/index/current_repo_map.md` if repo truth changed materially

## Doc ownership

This lane owns accepted updates in surfaces such as:

- `docs/plans/`
- `docs/issues/`
- `docs/gaps/`
- `docs/sdd/`
- `docs/project/`
- `docs/handoff/`
- `README.md`

Update only the surfaces actually changed by accepted work.

## Output rules

Write loop receipts to `.ai/dropbox/state/`.

Preferred artifacts:

- `accepted_loops.md`
- `open_questions.md`
- `rejections.md`

## Do not

- do not treat in-flight lane output as repo truth
- do not advance a story without evidence-backed acceptance
- do not let docs drift ahead of accepted code and validated behavior
