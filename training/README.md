# Training Workspace

This workspace is the repo-owned training surface for adaptive paper practice.

It exists to keep the long-running automation lane clean:

- SQL as canonical truth
- QMD as evidence
- `.ai/` as the live control plane
- `training/` as the durable code/config/prompt layer for autoresearch and evaluation

The training loop remains paper-only. It may adapt the active paper-practice
profile through bounded proposal review/comparison, but it must not widen into
live trading, mutate YAML policy, or self-edit runtime code.

## Layout

- `vendor/autoresearch/` — bounded vendored snapshot of `karpathy/autoresearch`
- `automation/` — adapted watcher/dispatcher pack for `codex --exec`
- `config/` — source-set and timeframe examples
- `rubrics/` — default evaluation rubrics
- `prompts/` — bounded prompt templates for reviews
- `bin/` — repo-owned helper scripts that bridge receipts into automation events

## Repo-owned CLI

Use the `d5 training ...` wrapper layer instead of ad hoc shell choreography:

- `d5 training bootstrap --json`
- `d5 training walk-forward --json`
- `d5 training review --json`
- `d5 training loop --max-iterations 1 --json`
- `d5 training status --json`

These wrappers sit on top of the adaptive paper-practice runtime and standardize
machine-readable receipts for `codex --exec`, tmux lanes, and watcher-driven
training review.

## Event-Driven Automation

The adapted watcher surface is intentionally small. The queue/receipt/log
workflow is useful for:

- session-close review prompts
- bounded backtest or experiment review prompts
- dry-run repair or docs-sync prompts

It is not the source of truth. It reads from SQL, JSON artifacts, and QMD
receipts that the engine already writes.
