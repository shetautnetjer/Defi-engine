# Trader CLI Crosswalk

This file is the truthful crosswalk between the repo's current CLI surface and
the longer-term trading grammar discussed in the companion Notion CLI page.

Use it to answer two questions quickly:

1. What commands exist right now?
2. What command families are still just north-star grammar?

The goal is clarity, not a speculative rename.

## Current truthful commands

### Capture and warehouse

- `d5 capture <provider>`
- `d5 training hydrate-history --json`
- `d5 training collect --json`
- `d5 sync-duckdb ...`

### Feature / condition / shadow

- `d5 materialize-features <feature-set>`
- `d5 score-conditions <condition-set>`
- `d5 run-shadow <shadow-run>`
- `d5 run-label-program <label-program>`
- `d5 run-strategy-eval <strategy-eval>`

### Live-paper preparation and paper execution

- `d5 run-live-regime-cycle`
- `d5 run-paper-cycle <quote_snapshot_id> --condition-run-id <id> --strategy-report <path>`
- `d5 run-paper-close <session_key> --quote-snapshot-id <id> --reason <reason>`
- `d5 run-paper-practice-bootstrap`
- `d5 run-paper-practice-loop`
- `d5 paper-practice-status`

### Training wrappers

- `d5 training bootstrap --json`
- `d5 training walk-forward --json`
- `d5 training review --json`
- `d5 training loop --max-iterations 1 --json`
- `d5 training status --json`

## North-star grammar

The Notion CLI page is directionally useful, but the repo does not yet expose a
fully normalized grammar like:

- `d5 source collect --provider ...`
- `d5 universe build --source ...`
- `d5 paper-live watch --venue ...`
- `d5 trader review --lane trader`

Treat those as north-star shapes only. They are not current repo truth.

## Current truthful commands vs north-star grammar

| Current truthful command | Nearest north-star family | Truth today |
| --- | --- | --- |
| `d5 capture jupiter-quotes` | `d5 source collect --provider jupiter` | Implemented |
| `d5 training hydrate-history` | `d5 source hydrate --provider massive` | Implemented as wrapper |
| `d5 materialize-features global-regime-inputs-15m-v1` | `d5 feature build --family regime` | Implemented |
| `d5 score-conditions global-regime-v1` | `d5 condition score --family regime` | Implemented |
| `d5 run-live-regime-cycle` | `d5 paper-live watch --lane trader` | Partially overlaps; still an explicit bounded live-cycle owner |
| `d5 run-paper-cycle ...` | `d5 paper execute --venue jupiter` | Implemented, but only from explicit quote snapshots |
| `d5 training review` | `d5 trader review --lane trader` | Implemented as wrapper |

## Source / venue matrix

| Source or venue | Current role | Paper-executable now | Storage role | Notes |
| --- | --- | --- | --- | --- |
| Jupiter | quote and spot execution context | Yes, for bounded `SOL/USDC` paper cycles | SQL receipts + raw source artifacts | Current truthful paper execution seam |
| Coinbase | market-data and futures/perps context | No | SQL + raw source artifacts | Context-only, not a paper execution venue |
| Massive | historical crypto backbone | No | raw `CSV.gz` + Parquet + SQL | Historical and replay/training only |
| Helius | Solana chain-state enrichment | No | raw JSONL + SQL | Deep on-chain context, not an execution venue |

## Interchangeability truth

There is no interchangeable paper-execution venue contract yet.

Truth today:

- Jupiter is the only paper-executable venue seam.
- Coinbase is context and market-data only.
- Massive is historical and replay/training only.
- Helius is Solana chain-state context only.

So the repo can train and paper trade today, but it cannot yet swap venues with
one flag and preserve identical paper execution behavior.

## Trader control plane

The repo now uses a named persistent `trader` lane and a fresh `task` lane for
Codex automation:

- `trader`
  - persistent
  - resumed with `codex exec resume <SESSION_ID>`
  - owns paper-session, experiment, and condition review continuity
- `task`
  - fresh one-shot runs
  - owns feature review and repair-style fixups

That lane split is automation truth; it is not a new `d5` command family.

## What to implement next

After the `trader` lane and CLI crosswalk are stable, the next major surface is
not a CLI rename. It is:

- protocol-aware Solana adapters
- deeper Helius entity/state warehousing
- paper-safe protocol strategy evaluation
- later, a more normalized domain grammar once those surfaces are real
