# Execution Intent Gap

## Stage

Closed in late Stage 1 before widening into later product stages.

## Current truth

The repo now has:

- explicit policy traces
- explicit hard risk gating
- explicit paper settlement

The remaining runtime-owner gap is no longer policy, risk, or settlement
themselves.

## Status

This gap is now closed by `EXEC-001`.

The repo now has one runtime-owned execution-intent surface between `risk/`
and `settlement/`.

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

## Why it mattered

Without execution intent, a market-wide allowed risk verdict does not become
governed paper action. Settlement still depends on explicit ids rather than a
runtime-owned decision path.

## Close evidence

- one bounded execution-intent contract exists
- it remains paper-only and spot-first
- settlement consumes execution intent instead of inferring hidden selection
- docs/tests clearly separate execution intent from policy promotion and live
  execution

## Landed truth

- `execution_intent/owner.py` owns `execution_intent_v1`
- the owner persists explicit mint, side, size, and entry intent from quote
  provenance
- `PaperSettlement` consumes `execution_intent_id`
- the surface stays bounded to paper-only spot entry intent with exit and stop
  semantics still marked `not_owned`
