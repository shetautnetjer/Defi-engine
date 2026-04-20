# Training Program V2 — Evidence-First Harness

## Mission

Run bounded, evidence-first training loops that improve D5 without granting hidden runtime authority.

## Current Target

Build a Solana/Jupiter/Coinbase paper-trading research harness with Massive historical warehouse support and Helius on-chain/supporting signals.

## Loop

```text
diagnose window
→ repair data/features if needed
→ run baseline
→ run candidate
→ compare
→ write evidence
→ propose next bounded test
```

## Required Diagnostic First

Before strategy tuning, run:

```bash
d5 diagnose training-window --regimen quickstart_300d --json
d5 diagnose gate-funnel --run latest --json
d5 diagnose no-trades --run latest --window 300d --json
```

For agent quickreads, use the read-only Rust verifier:

```bash
cargo run --manifest-path rust/Cargo.toml --bin d5v -- coverage --regimen full_730d --json
cargo run --manifest-path rust/Cargo.toml --bin d5v -- funnel --run latest-populated --json
cargo run --manifest-path rust/Cargo.toml --bin d5v -- no-trades --run latest --window 730d --json
```

## Evidence Rollup First

Before generating new proposals, run:

```bash
d5 training evidence-rollup --json
d5 training evidence-gap --json
```

## Mutation Law

The training loop may create candidate overlays.
It may not directly mutate approved runtime authority.

## Batches

Every experiment batch must include:

- one mainline candidate
- one isolate-cause candidate
- one falsification/sanity candidate

## Stop Conditions

Stop and write a proposal instead of patching if:

- the task touches risk limits
- the task touches live execution
- the task would widen providers
- the task requires a new strategy family promotion
- the task lacks a baseline
