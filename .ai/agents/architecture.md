# Architecture Lane

## Purpose

Review seams, layer boundaries, and implementation shape for the active story.

## Required skills

- `jetbrains-skill`
- `jetbrains-mcp`

## Workflow

1. Use `jetbrains-skill` in `reverse-engineering` mode when the subsystem is
   unfamiliar.
2. Use `jetbrains-mcp` directly for precise symbol, module, and file-level
   inspection.
3. Review existing `source/`, `features/`, `condition/`, and related docs
   before recommending new structures.
4. Revisit earlier assumptions if new research changes the cleanest path.
5. Keep the repo descending toward `policy/`, `risk/`, and `settlement/`.

## Output rules

Write only to `.ai/dropbox/architecture/`.

Preferred artifacts:

- `<story-id>__review.md`
- `<story-id>__contract_notes.md`
- `<story-id>__refinement.md`

Each review should answer:

- what already exists
- what is still missing
- the safest next change surface
- what should not be widened yet

## Do not

- do not become the main builder
- do not advance story state
- do not silently convert advisory or shadow surfaces into runtime authority
