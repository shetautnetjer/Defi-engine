# Source Map and Source Completeness

## Purpose

Define the current provider-role map and the minimum completeness standard that a source lane must satisfy before downstream runtime layers should depend on it.

This note is a planning surface. Code, schemas, and tests remain the active truth for what is implemented now.

## Current Provider Roles

| Provider | Role now | Current status | Downstream caution |
|------|-------|-------|-------|
| Jupiter | Solana spot reference pricing and two-sided quote capture | implemented | use as spot reference only; do not treat it as execution authority |
| Helius | Solana chain discovery, tracked-address expansion, enhanced transaction receipts, and bounded transfer projection | partial | current canonical projection is intentionally narrow and should not be mistaken for protocol-complete chain semantics |
| Coinbase | public market-data venue for products, candles, trades, and L2 book snapshots | partial | market-data source only; not an execution venue in current repo truth |
| FRED | macro context source for series and observations | implemented | useful for later features and condition work, not for direct trade execution logic |
| Massive | future historical depth and research support | scaffolded | fail-closed until entitlement, endpoint proof, and payload shape are confirmed |

## Source Completeness Standard

A source lane should not be treated as runtime-ready until it has all of the following:

1. raw receipt path
   - payloads land with stable provenance and replayable metadata
2. canonical projection
   - the source has a documented normalized output in SQLite truth tables
3. health and failure semantics
   - capture success, throttling, entitlement failure, and stale-source conditions are explicit
4. time authority
   - provider event time is preserved when available and UTC helpers are materialized for downstream use
5. bounded role claim
   - the repo docs say what the source is for, and what it is not for

## Role Boundaries

- Jupiter
  - role: current spot quote and token metadata reference
  - not a paper execution venue
- Helius
  - role: chain-state and tracked-address truth support
  - not a claim of full Solana program decoding
- Coinbase
  - role: centralized spot market-data contrast surface
  - not a claim of order routing, auth trading, or fill simulation
- FRED
  - role: macro context enrichment
  - not a short-horizon trading trigger by itself
- Massive
  - role: future historical depth and walk-forward research support
  - not an active runtime dependency today

## Current Completeness Read

- Jupiter
  - strongest current runtime-ready source lane for downstream feature use
- Helius
  - usable for bounded transfer and registry work, but still incomplete for deeper protocol-aware reasoning
- Coinbase
  - usable for market-data feature work, but still incomplete for any execution or slippage assumptions
- FRED
  - usable for macro feature inputs once features/materialization exists
- Massive
  - not yet eligible for downstream dependency

## Next Source-Doctrine Follow-Ons

- write the first feature-input contract that names exactly which canonical tables each downstream layer may consume
- define source freshness and completeness thresholds for continuous capture ownership
- add a DeFi-specific provider map once richer chain-event semantics and protocol-aware decoding are real
