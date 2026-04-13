# engineering-flow.md

## Purpose
Define the default engineering loop for agents working in this repo.

## Scope
Use this playbook for:
- feature work
- bug fixes
- refactors explicitly requested by the operator
- schema/config/doc/test synchronization

## Engineering Rules
- Reconstruct current behavior before proposing changes.
- Read the touched code path end to end before patching.
- Prefer narrow patches over architecture drift.
- Keep ownership boundaries visible.
- If a task changes behavior, update tests and docs/config together.
- If a task is cross-layer, identify one integration owner and keep the rest additive.

## Required Working Loop
1. Intake the task.
2. Identify touched files, modules, and owning layer.
3. Read current code, config, docs, and tests in that area.
4. State the current behavior in concrete terms.
5. Make the smallest patch that satisfies the task.
6. Run relevant checks.
7. Produce a receipt.

## Patch Discipline
- Do not rename or move large trees unless explicitly requested.
- Do not widen provider, asset, or runtime scope unless explicitly approved.
- Do not silently change defaults that affect trading behavior.
- Do not hide critical behavior in helpers or magic config.
- Do not claim a refactor is behavior-preserving without a validation path.

## Required Validations
Choose the strongest relevant checks, such as:
- targeted unit tests
- integration tests for touched flows
- schema validation
- lint/type checks where available
- replay or deterministic paper-flow checks for trading paths

## Receipt Format
Every non-trivial change should end with:
- files changed
- why they changed
- commands run
- results
- docs/tests/config updated or not
- known gaps or risk

## Escalation Triggers
Escalate or stop and mark governance-sensitive if the task touches:
- strategy eligibility
- risk gates
- runtime authority
- promotion status
- live execution behavior
