# Execution Intent Gap

## Stage

Late Stage 1 before widening into later product stages.

## Current truth

The repo now has:

- explicit policy traces
- explicit hard risk gating
- explicit paper settlement

The remaining runtime-owner gap is no longer policy, risk, or settlement
themselves.

## Gap

The repo still lacks one runtime-owned execution-intent surface between
`risk/` and `settlement/`.

That surface should define:

- instrument
- venue
- strategy family
- side
- size logic
- entry logic
- exit logic
- stop logic
- why policy allowed it
- why risk allowed it
- what settlement model applies

## Why it matters

Without execution intent, a market-wide allowed risk verdict does not become
governed paper action. Settlement still depends on explicit ids rather than a
runtime-owned decision path.

## Close when

- one bounded execution-intent contract exists
- it remains paper-only and spot-first
- settlement consumes execution intent instead of inferring hidden selection
- docs/tests clearly separate execution intent from policy promotion and live
  execution
