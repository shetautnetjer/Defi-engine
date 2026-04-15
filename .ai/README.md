# Defi-engine Agent Orchestration

This directory is the repo-local control surface for Ralph-style tmux work in
`Defi-engine`.

It is intentionally split into four concerns:

- `agents/`
  - lane-specific guidance derived from repo doctrine
- `index/`
  - current repo truth so lanes do not invent already-existing surfaces
- `templates/`
  - lane prompt files for `codex exec` or other lane launchers
- `dropbox/`
  - shared handoff area for live lane outputs

The canonical story ledger does **not** live in this directory.

- `prd.json`
  - active story ledger
- `progress.txt`
  - append-only carry-forward state

The `dropbox/` subdirectories are tracked only for structure. Live lane output
inside them is ignored by Git unless explicitly staged.
