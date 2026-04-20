# D5V Rust Verifier

## Purpose

`d5v` is a read-only Rust verifier for D5 training and runtime evidence loops.

It gives Codex and operator workflows fast, deterministic JSON quickreads before proposal, replay, promotion, or no-trade diagnosis work.

## Authority

`d5v` may:

- read repo files, schemas, policies, and SQLite evidence
- aggregate decision-funnel and training-window evidence
- validate import boundaries, JSON contracts, and secret leaks
- write `.ai/quickreads/*.json` receipts

`d5v` may not:

- mutate SQL truth
- change policy, risk, strategy, label, or feature configs
- route orders or sign Solana transactions
- promote candidates
- weaken risk controls

## Commands

```bash
cargo run --manifest-path rust/Cargo.toml --bin d5v -- coverage \
  --repo-root . \
  --db-path data/db/d5.db \
  --regimen full_730d \
  --json

cargo run --manifest-path rust/Cargo.toml --bin d5v -- funnel \
  --repo-root . \
  --db-path data/db/d5.db \
  --run latest-populated \
  --json

cargo run --manifest-path rust/Cargo.toml --bin d5v -- no-trades \
  --repo-root . \
  --db-path data/db/d5.db \
  --run latest \
  --window 730d \
  --json

cargo run --manifest-path rust/Cargo.toml --bin d5v -- boundaries \
  --repo-root . \
  --json

cargo run --manifest-path rust/Cargo.toml --bin d5v -- schema-check \
  --repo-root . \
  --all \
  --json

cargo run --manifest-path rust/Cargo.toml --bin d5v -- secrets \
  --repo-root . \
  --json
```

Use `--no-write-quickread` when a caller wants stdout-only output.

Use `--run latest` to test the newest loop run even if it has zero decisions. Use `--run latest-populated` when the caller needs the newest loop that actually has decision evidence.

## Quickread Contract

Each command emits a stable JSON object:

```json
{
  "tool": "d5v.funnel",
  "version": "v1",
  "created_at_utc": "2026-04-20T00:00:00Z",
  "repo_ref": {
    "git_commit": "unknown",
    "branch": "unknown"
  },
  "verdict": "PASS",
  "primary_failure_surface": null,
  "summary": {},
  "details": {},
  "recommended_next_actions": []
}
```

The quickread files live under `.ai/quickreads/` and are ignored except for the directory placeholder.

## Training Role

Before changing candidate overlays or proposing strategy/risk/policy work, run the relevant quickreads.

If a no-trade window fails, use the reported `primary_failure_surface` to select one bounded experiment batch. Do not skip directly to strategy changes.

## Current V1 Scope

V1 verifies:

- training-window SQL and feature coverage
- paper-practice decision funnel counts
- no-trade reason-code rollups
- missing decision-funnel execution receipts
- runtime/research import-boundary violations
- schema/policy JSON parse validity
- obvious tracked private-key material

V1 does not execute a useful 730-day replay by itself. It provides the evidence packet that the Python research/training loop should use to choose and verify that replay.
