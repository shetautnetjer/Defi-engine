# Strategy Descent and Instrument Scope

This note defines which instruments and strategy classes are allowed at each
stage of the product descent.

## Stage ladder

### Stage 1 — Solana spot paper truth

Allowed focus:

- mint-locked Solana spot instruments
- governed paper settlement
- explicit feature, regime, policy, and risk ownership
- bounded strategy eligibility and paper reporting

Prerequisites to leave this stage:

- continuous capture ownership is explicit
- execution intent exists between `risk/` and `settlement/`
- realized-feedback comparison is wired into `research_loop/`

### Stage 2 — Jupiter spot strategy depth

Allowed focus:

- multiple bounded spot strategy classes
- stronger venue-aware quote and fee assumptions
- strategy comparison across regimes
- paper session reporting that can compare strategy families honestly

Do not widen to leverage yet.

### Stage 3 — Jupiter perps

Allowed only after:

- spot paper truth is stable
- liquidation and leverage assumptions are explicit
- perps-specific fill, funding, and session logic are modeled
- risk surfaces can veto leverage-aware failure modes explicitly

### Stage 4 — Coinbase futures

Allowed only after:

- the perps expansion rules are already understood
- futures-specific contracts, session boundaries, and fee assumptions are explicit
- the backtesting truth layer can distinguish venue and instrument family cleanly

## Strategy classes by stage

Stage 1 and Stage 2 may support:

- regime-filtered directional spot strategies
- bounded trend-following and reversal entries
- shadow-only forecasting comparators
- strategy comparison under explicit fees and slippage assumptions

Stage 3 and Stage 4 may add:

- leverage-aware directional strategies
- liquidation-sensitive protection logic
- venue-specific carry or funding-aware strategies

## What remains deferred

Deferred until later-stage widening:

- live trading
- hidden venue inference from risk alone
- perps or futures implied by research output
- broad multi-venue strategy expansion without explicit truth surfaces

These remain future-stage concerns until the lower paper-runtime and
backtesting truth surfaces are strong enough to widen safely.

## Contract rule

Instrument widening is a governed capability stage, not a modeling side
effect. A model that “looks good” on shadow evidence does not widen scope by
itself.
