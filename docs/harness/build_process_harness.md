# Build Process Harness

## Purpose

Define how the agent should build the system without getting lost in repo clutter.

## Build Order

1. Truth surface cleanup
2. Runtime/research/control-plane boundary check
3. Evidence-to-experiment loop
4. No-trade/gate-funnel diagnostics
5. Training-window coverage diagnostics
6. Candidate overlay scaffolding
7. Promotion packet scaffolding
8. Micro-live gate docs only

## One-Slice Rule

Every implementation task must name exactly one primary surface:

- source
- storage
- features
- condition
- policy
- risk
- execution_intent
- settlement
- research_loop
- reporting
- training
- codex_harness
- docs_truth

## Boundary Rules

- runtime core must not import training
- runtime core must not import `.ai`
- runtime core must not import Codex harness logic
- training may call runtime through CLI/contracts
- Codex may call runtime/training through CLI/contracts
- docs may describe but not authorize runtime behavior

## Validation Rule

Every slice must produce:

- files changed
- commands run
- tests/checks run
- receipts
- open risks
- next seam

## Best First Build

Implement diagnostic visibility before new strategy complexity.

First code target:

```bash
d5 diagnose training-window --regimen quickstart_300d --json
d5 diagnose gate-funnel --run latest --json
d5 diagnose no-trades --run latest --window 300d --json
```
