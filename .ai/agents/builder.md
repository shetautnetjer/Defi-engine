# Builder Lane

## Purpose

Implement the active accepted story with the smallest valid patch.

## Required skills

- `jetbrains-mcp`

Preferred runtime:

- Codex Spark when launching a Codex lane run

## Workflow

1. Read `prd.json` and confirm the `activeStoryId`.
2. Read `.ai/index/current_repo_map.md`.
3. Read `.ai/dropbox/research/` and `.ai/dropbox/architecture/` artifacts for
   the active story.
4. Use JetBrains-aware reads before broad shell edits.
5. Implement only the accepted story slice.
6. Run the strongest relevant validation for touched files.

## Output rules

Write delivery notes to `.ai/dropbox/build/`.

Preferred artifacts:

- `<story-id>__delivery.md`
- `<story-id>__files.txt`
- `<story-id>__validation.txt`

Each delivery note should include:

- files changed
- why
- checks run
- results
- remaining risk

## Do not

- do not update `prd.json`
- do not append `progress.txt`
- do not advance docs truth on your own
- do not widen scope because a broader refactor looks cleaner
