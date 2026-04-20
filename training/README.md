# Training Workspace

This workspace is the repo-owned training surface for adaptive paper practice.

## Grounding

- Companion Notion reference: [Training regime](https://www.notion.so/Training-regime-347936b02c25803d8ec4cb77cf4040d6?source=copy_link)
- Companion Notion reference: [Codex trader harnesses](https://www.notion.so/Codex-trader-harnesses-347936b02c25806bad8bd6a5fde8c51d?source=copy_link)
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
7. `.ai/profiles.toml`
8. `.ai/schemas/profile.schema.json`
9. `.ai/policies/profile_router_policy.v1.json`
10. `.ai/prompts/profile_governor_turn.md`
11. `docs/project/current_runtime_truth.md`

It exists to keep the long-running automation lane clean:

- SQL as canonical truth
- Parquet as the deep-history warehouse
- QMD as evidence
- `.ai/` as the live control plane
- `training/` as the durable code/config/prompt layer for autoresearch and evaluation

The default training loop remains paper-first. It may adapt the active
paper-practice profile through bounded proposal review/comparison, and later
V2 candidate overlays may test labels, features, strategy policy, and risk
variants in research or paper lanes. Those overlays do not grant runtime
authority by themselves.

Micro-live Jupiter execution is a separate governed ladder. It may only run
after readiness gates pass, an explicit expiring arm state exists, and an
external signer is configured. The repo must not store or print raw Solana
private-key material.

The current automation split is:

- `.codex/config.toml` and `.codex/hooks.json` for repo-local Codex profiles and hook plumbing
- persistent `trader` lane for resumed review continuity
- fresh `task` lane for one-shot repair/review work
- `training/automation/state/lane_sessions.json` for lane session stewardship

## Layout

- `vendor/autoresearch/` — bounded vendored snapshot of `karpathy/autoresearch`
- `automation/` — adapted watcher/dispatcher pack for `codex exec` and `codex exec resume`
- `config/` — source-set and timeframe examples
- `trading_agent_harness.md` — trading-focused Codex harness doctrine for bounded training and paper review work
- `rubrics/` — default evaluation rubrics
- `rubrics/training_regime_rubric.md` — stage-gated training rubric mirrored from the companion Notion page
- `prompts/` — bounded prompt templates for reviews
- `bin/` — repo-owned helper scripts that bridge receipts into automation events
- `program.md` — repo-owned governed autoresearch contract for this training lane

## Repo-owned CLI

Use the `d5 training ...` wrapper layer instead of ad hoc shell choreography:

- `d5 hydrate-history --training-regimen auto --json`
- `d5 training bootstrap --json`
- `d5 training hydrate-history --training-regimen auto --json`
- `d5 training collect --json`
- `d5 training walk-forward --training-regimen auto --json`
- `d5 training review --json`
- `d5 training loop --max-iterations 1 --json`
- `d5 training status --json`
- `d5 training evidence-gap --json`
- `d5 training experiment-batch --json`
- `d5 diagnose training-window --regimen quickstart_300d --json`
- `d5 diagnose gate-funnel --run latest --json`
- `d5 diagnose no-trades --run latest --window 300d --json`
- `d5 live-readiness --json`
- `d5 micro-live status --json`
- `d5 micro-live arm --max-notional-usdc 2 --daily-loss-limit-usdc 1 --weekly-loss-limit-usdc 2 --json`

These wrappers sit on top of the adaptive paper-practice runtime and standardize
machine-readable receipts for `codex --exec`, tmux lanes, and watcher-driven
training review.

`d5 training evidence-gap --json` is the first evidence-rollup seam. It reads
paper-practice SQL decisions and the latest no-trade feedback receipts, ranks
current failure families, and selects the next tiny comparable experiment batch.
It should produce revisable hypotheses and candidate-overlay targets, not runtime
authority.

`d5 training experiment-batch --json` is the first proposal-batch seam. It reads
the ranked evidence gap, chooses one failure family, writes candidate overlay
JSONs under `data/research/training/experiment_batches/`, and creates advisory
`improvement_proposal_v1` rows for each candidate. These overlays are
research/shadow evidence only: they do not alter YAML policy, risk behavior,
paper runtime authority, or live order routing.

`d5 diagnose ... --json` is the runtime funnel seam. It answers whether the
selected training window has enough SQL/features, how far the latest
paper-practice run moved through condition/policy/risk/quote/fill gates, and why
the current window produced no or few trades. These commands write JSON/QMD
diagnostic receipts under `data/research/training/diagnostics/` and latest-state
copies under `.ai/dropbox/state/`.

The paper-practice training regimen is now selectable:

- `auto` is the default and chooses the fastest ready regimen so paper training can start once `quickstart_300d` is satisfied
- `full_730d` keeps the heavier long-history path available when it is explicitly selected
- `quickstart_300d` allows an earlier paper-only bootstrap once roughly 300 days are available

These regimens control history depth, warmup, and replay shape only. They do not
hard-wire strategy, policy, or risk behavior.

Research profiles are a separate concept. They should express search bias such as
momentum, mean reversion, wallet flow, cost sensitivity, or preferred market
horizons. They are not runtime authority. The repo-owned machine-readable pack
lives in `.ai/profiles.toml`, with `.ai/schemas/profile.schema.json` as the
validator and `training/config/research_profiles.example.toml` retained as a
companion example surface.

The profile governor is a thin overlay on top of that pack. Its machine-readable
surfaces live in `.ai/policies/profile_router_policy.v1.json`,
`.ai/schemas/meta_governor_scorecard.schema.json`,
`.ai/schemas/profile_router_policy.schema.json`,
`.ai/schemas/profile_governor_decision.schema.json`, and
`.ai/prompts/profile_governor_turn.md`. It should route or score existing
proposal/comparison evidence, not replace runtime policy or risk ownership.

The intended operating shape is:

- hydrate the selected Massive-backed training-regimen window first and keep it locally
- use chunked Massive REST range calls (`limit=50000` per ticker request) when flat files are unavailable
- preserve raw source artifacts and partitioned Parquet for replay and research
- reuse local SQL + local warehouse artifacts for replay, walk-forward, review, and QMD evidence
- append only the missing historical days for the selected regimen or the full cache when explicitly requested
- after that, keep running incremental source collection for Massive/Coinbase/Jupiter/Helius
- once the selected training regimen is ready and bootstrapped, run the continuous live paper-practice loop
- after paper-practice decisions accumulate, run `d5 training evidence-gap --json`
  so no-trade cycles become comparable experiment batches instead of passive logs

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

The continuous paper-training steward is separate from that event watcher:

- start it with `ATTACH=0 training/automation/tmux/start_training_supervisor_tmux.sh`
- it follows the selected training regimen from `d5 training status --json`
- it bootstraps once the selected regimen is ready, even if the full Massive
  730-day cache still has a partial missing day
- after bootstrap it cycles source collection, training review, and one
  paper-practice loop iteration without widening live authority
