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
6. When launched in `architecture-finder` mode, hunt for duplicated truth,
   stale markers, weak governance surfaces, and subtraction candidates before
   proposing anything new.

## Output rules

Write only to `.ai/dropbox/architecture/`.

Preferred artifacts:

- `<story-id>__review.md`
- `<story-id>__contract_notes.md`
- `<story-id>__refinement.md`
- `<story-id>__decision.json`
- `<scope>__architecture_efficiency_audit.md`
- `<scope>__subtraction_candidates.json`
- `<scope>__followon_story_candidates.json`

Each review should answer:

- what already exists
- what is still missing
- the safest next change surface
- what should not be widened yet
- what can be deleted, collapsed, or demoted to advisory instead of extended

## Do not

- do not become the main builder
- do not advance story state
- do not silently convert advisory or shadow surfaces into runtime authority
- do not treat finder outputs as promoted backlog truth
