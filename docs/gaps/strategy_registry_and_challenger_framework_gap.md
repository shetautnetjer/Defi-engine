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

## Gap

The repo still lacks:

- a strategy registry with named strategy families
- a machine-readable metrics registry
- explicit champion-versus-challenger comparison rules
- promotion-candidate artifacts for strategy-family work

## Why it matters

Without a strategy registry, the system risks devolving into one giant
all-purpose modeling surface instead of many bounded, regime-aware strategy
families.

## Close when

- strategy families are named and documented
- each family declares valid instruments, regimes, labels, and feature sets
- challenger reports and promotion-candidate artifacts exist
- model and strategy comparisons are evaluated by explicit governance metrics
