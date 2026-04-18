# Training AGENTS

## Mission

Keep autoresearch and evaluation inside a paper-only, reviewable, repo-owned
training lane.

## Ground Rules

- paper-only
- SQL remains canonical truth
- QMD remains evidence
- `.ai/` remains the live control plane
- `training/` owns prompts, rubrics, wrappers, and automation adapters
- one bounded thing at a time

## What This Folder Owns

- vendored upstream training references
- watcher and `codex --exec` adapters
- source-set and timeframe configs
- evaluation rubrics
- prompt templates
- event-bridge helpers

## What This Folder Does Not Own

- settlement ledgers
- runtime policy YAML
- risk gate code
- provider adapters
- canonical database schemas

Training may recommend or auto-apply bounded paper-profile revisions only when
they pass the existing proposal review and comparison flow.
