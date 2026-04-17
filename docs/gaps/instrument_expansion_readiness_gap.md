# Instrument Expansion Readiness Gap

## Stage

Stage 6: instrument expansion.

## Current truth

Current truthful scope remains paper-first and bounded.

The repo is strongest in Solana and Jupiter spot-oriented work. Perps and
futures remain future-stage targets.

## Gap

The repo does not yet have a governed readiness contract for widening into:

- deeper Jupiter spot strategy support
- Jupiter perp paper semantics
- Coinbase futures paper semantics

## Why it matters

Every widening multiplies:

- slippage assumptions
- liquidation logic
- leverage risk
- session semantics
- venue-specific behavior

Without readiness rules, research and runtime scopes can drift into derivatives
before the lower spot-only truth surfaces are strong enough.

## Close when

- the widening ladder is treated as a governed gate rather than a wishlist
- explicit readiness criteria exist for each new instrument family
- perps and futures paper semantics are documented separately from spot
- the repo can show why each widened surface is eligible rather than merely
  interesting
