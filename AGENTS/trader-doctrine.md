# trader-doctrine.md

## Purpose
Define the repo's trading law for engineering agents, research agents, and policy agents.

## Core Doctrine
- Capital preservation first.
- Paper trading first.
- Default safe action is no-trade.
- Models suggest; the engine decides.
- Risk controls are mandatory and non-bypassable.
- Memory and LLM systems are advisory only.

## Hard Trading Guardrails
- No live order placement unless the operator explicitly widens scope.
- No change may bypass the risk gate.
- No agent may silently make a strategy runtime-eligible.
- No agent may weaken halts, cooldowns, sizing caps, or stale-data checks without explicit approval.
- Trajectory, forecasting, and advanced research signals are advisory until promoted through evidence.

## Runtime Authority Order
1. current code/config/schema truth
2. approved policy snapshots
3. strategy eligibility and parameter surfaces
4. risk gate
5. paper execution and settlement

Forecasts, memory, and editor tooling sit outside this runtime authority chain.

## Trading State Rules
When any of the following is true, prefer no-trade or defensive paper-only behavior:
- stale feed
- ambiguous policy
- weak or conflicting evidence
- anomaly flag active
- missing validation
- missing reproducibility

## Acceptable Agent Actions
Agents may:
- improve paper simulation
- improve observability and audit surfaces
- improve condition detection
- improve feature quality
- propose bounded experiments
- compare strategies and regimes

Agents may not:
- self-promote a model
- invent runtime authority from advisory signals
- mutate policy implicitly in code
- mix shadow features into approved runtime without promotion

## Required Trading Receipts
For trading-sensitive changes, receipts must include:
- trading surface touched
- policy/risk impact
- validation run
- whether runtime authority changed
- whether the change is shadow-only, paper-approved, or governance-sensitive
