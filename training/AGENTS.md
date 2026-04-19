# Training AGENTS

## Companion References

- Notion companion: [Training regime](https://www.notion.so/Training-regime-347936b02c25803d8ec4cb77cf4040d6?source=copy_link)

Use the Notion page as a companion reference for the training rubric and
program framing. Repo-owned files in `training/` remain the durable
implementation truth for this workspace.

## Mission

Keep autoresearch and evaluation inside a paper-only, reviewable, repo-owned
training lane.

The automation in this folder should behave like a trading-focused harness that
gets better at evidence-based paper trading over time, not like a generic repo
bot.

## Ground Rules

- paper-only
- SQL remains canonical truth
- QMD remains evidence
- `.ai/` remains the live control plane
- `training/` owns prompts, rubrics, wrappers, and automation adapters
- one bounded thing at a time

## Superpowers Routing

- use `superpowers:writing-plans` before changing the training doctrine or multi-step automation contracts
- use `superpowers:executing-plans` when implementing an accepted training/runtime plan
- use `superpowers:systematic-debugging` before changing the harness after a failing review or verification loop
- use `superpowers:verification-before-completion` before claiming the trading harness or storage/reporting slice is done

## Read Order

1. repo root `AGENTS.md`
2. this file
3. `training/README.md`
4. `training/trading_agent_harness.md`
5. `training/program.md`
6. `training/rubrics/training_regime_rubric.md`
7. `docs/task/trading_qmd_report_contract.md`
8. linked runtime and project truth docs

## What This Folder Owns

- vendored upstream training references
- trading-harness doctrine
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
