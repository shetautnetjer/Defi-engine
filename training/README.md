# Training Workspace

This workspace is the repo-owned training surface for adaptive paper practice.

## Grounding

- Companion Notion reference: [Training regime](https://www.notion.so/Training-regime-347936b02c25803d8ec4cb77cf4040d6?source=copy_link)
- Root policy and execution law: `AGENTS.md`
- Local grounding guide: `training/AGENTS.md`
- Trading harness doctrine: `training/trading_agent_harness.md`
- Local operating contract: `training/program.md`
- Local rubric mirror: `training/rubrics/training_regime_rubric.md`
- QMD evidence contract: `docs/task/trading_qmd_report_contract.md`

The Notion page is stronger on rubric and autoresearch program framing. The
repo-owned docs here are stronger on actual CLI surfaces, SQL/QMD truth, and
the behavior this codebase already supports. Read both, but implement from the
repo-owned docs first.

## Read This First

1. `training/AGENTS.md`
2. this README
3. `training/trading_agent_harness.md`
4. `training/program.md`
5. `training/rubrics/training_regime_rubric.md`
6. `docs/task/trading_qmd_report_contract.md`
7. `docs/project/current_runtime_truth.md`

It exists to keep the long-running automation lane clean:

- SQL as canonical truth
- Parquet as the deep-history warehouse
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
- `trading_agent_harness.md` — trading-focused Codex harness doctrine for bounded training and paper review work
- `rubrics/` — default evaluation rubrics
- `rubrics/training_regime_rubric.md` — stage-gated training rubric mirrored from the companion Notion page
- `prompts/` — bounded prompt templates for reviews
- `bin/` — repo-owned helper scripts that bridge receipts into automation events
- `program.md` — repo-owned governed autoresearch contract for this training lane

## Repo-owned CLI

Use the `d5 training ...` wrapper layer instead of ad hoc shell choreography:

- `d5 training bootstrap --json`
- `d5 training hydrate-history --json`
- `d5 training collect --json`
- `d5 training walk-forward --json`
- `d5 training review --json`
- `d5 training loop --max-iterations 1 --json`
- `d5 training status --json`

These wrappers sit on top of the adaptive paper-practice runtime and standardize
machine-readable receipts for `codex --exec`, tmux lanes, and watcher-driven
training review.

The intended operating shape is:

- hydrate the Massive historical backbone once and keep it locally
- preserve raw CSV.gz artifacts and partitioned Parquet for replay and research
- reuse local SQL + local warehouse artifacts for replay, walk-forward, review, and QMD evidence
- append only the missing historical days until the cache is complete
- after that, keep running incremental source collection for Massive/Coinbase/Jupiter/Helius
- only then run the continuous live paper-practice loop

In other words, `training collect` should append new source data. It should not
repull the full historical window once the cache is complete.

## Event-Driven Automation

The adapted watcher surface is intentionally small. The queue/receipt/log
workflow is useful for:

- session-close review prompts
- bounded backtest or experiment review prompts
- dry-run repair or docs-sync prompts

It is not the source of truth. It reads from SQL, JSON artifacts, and QMD
receipts that the engine already writes.

When the watcher dispatches Codex, it should treat `training/AGENTS.md`,
root `AGENTS.md`, `training/trading_agent_harness.md`, `training/program.md`, and
`training/rubrics/training_regime_rubric.md` as the main local doctrine stack.
