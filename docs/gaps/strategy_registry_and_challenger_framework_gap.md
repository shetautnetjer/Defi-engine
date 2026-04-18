# Strategy Registry And Challenger Framework Gap

## Stage

Stage 4 and Stage 5: strategy research plus governed promotion.

## Current truth

The shadow lane already combines:

- deterministic feature inputs
- walk-forward regime history
- bounded labels
- anomaly flags
- tabular challenger families such as RandomForest and XGBoost
- optional Chronos-2, Monte Carlo, and Fibonacci research annotations

It already has the core bounded model families that should anchor the first
repeated advisory challenger loop:

- `IsolationForest`
- `RandomForestClassifier`
- `XGBClassifier`

## Gap

The repo still lacks:

- accepted strategy-registry doctrine in the docs packet
- accepted machine-readable metrics doctrine in the docs packet
- explicit champion-versus-challenger comparison rules
- promotion-candidate artifacts for strategy-family work
- a bounded no-HITL advisory runner that can:
  - replay backtests repeatedly
  - run walk-forward comparisons repeatedly
  - score challenger families repeatedly
  - emit writer-routable proposal artifacts

## Why it matters

Without an accepted strategy registry, the system risks devolving into one giant
all-purpose modeling surface instead of many bounded, regime-aware strategy
families even though the first registry files now exist.

Without a repeated challenger loop, even named strategy families will stay too
manual and too slow to evolve toward the north star.

## Close when

- strategy families are named and documented
- each family declares valid instruments, regimes, labels, and feature sets
- challenger reports and promotion-candidate artifacts exist
- model and strategy comparisons are evaluated by explicit governance metrics
- repeated advisory scoring exists for the bounded challenger families already
  present in the repo
- bounded research proposal review can move advisory strategy work forward
  without granting runtime authority
