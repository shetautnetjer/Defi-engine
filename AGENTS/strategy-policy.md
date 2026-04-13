# strategy-policy.md

## Purpose
Define how agents may work on strategy logic, strategy eligibility, and policy surfaces without causing authority drift.

## Policy vs Implementation Law
Keep these separate:
- policy = which strategies are allowed, when, and with what parameter surface
- implementation = deterministic code that evaluates a strategy inside the approved surface

Agents must not blur these two roles.

## What Counts as Policy
Policy includes:
- approved strategy registry
- eligibility rules by regime or context
- parameter surfaces and overrides
- no-trade states
- instrument or venue allow/deny rules

## What Counts as Implementation
Implementation includes:
- deterministic signal evaluation
- rule calculations
- context building for strategy code
- traceable proposal generation

## Rules for Agents
- Do not make a strategy eligible by changing implementation code alone.
- Do not hide policy changes inside defaults.
- Do not change runtime thresholds without leaving an explicit trace.
- Do not allow advisory models to become direct strategy selectors by implication.
- Preserve explicit no-trade outcomes as first-class results.

## Allowed Changes
Agents may:
- improve a strategy implementation within existing policy limits
- add traceability to decisions
- add or tighten tests around strategy behavior
- propose policy changes as bounded artifacts

## Governance-Sensitive Changes
Treat these as governance-sensitive:
- adding a new strategy family to the approved runtime set
- changing regime-to-strategy mappings
- loosening cooldowns, caps, or filters
- adding trajectory-dependent policy influence
- changing defaults that affect strategy activation

## Required Receipts for Policy-Touching Work
- which policy surface changed
- which implementation surface changed
- whether eligibility changed
- whether parameter defaults changed
- validation performed
- whether operator approval is required before runtime use
