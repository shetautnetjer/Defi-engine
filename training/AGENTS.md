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
4. `.codex/config.toml` and `.codex/hooks.json`
5. `.ai/profiles.toml` and `.ai/schemas/profile.schema.json`
6. `.ai/policies/profile_router_policy.v1.json` and `.ai/prompts/profile_governor_turn.md`
7. `training/trading_agent_harness.md`
8. `training/program.md`
9. `training/rubrics/training_regime_rubric.md`
10. `docs/task/trading_qmd_report_contract.md`
11. linked runtime and project truth docs

## What This Folder Owns

- vendored upstream training references
- trading-harness doctrine
- watcher and `codex --exec` adapters
- named lane/session stewardship for `trader` and `task`
- source-set and timeframe configs
- evaluation rubrics
- prompt templates
- event-bridge helpers
- profile governor prompt and policy surfaces

## What This Folder Does Not Own

- settlement ledgers
- runtime policy YAML
- risk gate code
- provider adapters
- canonical database schemas

Training may recommend or auto-apply bounded paper-profile revisions only when
they pass the existing proposal review and comparison flow.

## Runtime Artifact Hygiene

- `training/automation/logs/`, `training/automation/receipts/`, and
  `training/automation/state/` are runtime output, not durable source.
- Promote only summarized decisions, accepted receipts, or stable config changes
  into tracked docs/config/tests.
- When a training loop produces useful but noisy artifacts, copy or compress
  them under ignored `data/archive/training/` and reference that archive from a
  handoff, journal entry, or accepted receipt.
