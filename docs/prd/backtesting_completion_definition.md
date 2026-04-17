# Backtesting Completion Definition

This file defines what “complete” means at each product stage so the swarm does
not confuse active experimentation with governed product completion.

## Stage completion meanings

### Bounded spot paper backtesting complete

This stage is complete when:

- paper settlement is truthful and replayable
- fill assumptions are explicit
- fees and slippage assumptions are explicit
- strategy comparison can run against governed paper outcomes

### Regime classification complete

This stage is complete when:

- regime taxonomy is explicit
- label taxonomy is explicit
- direction and regime metrics are replayable
- invalid / uncertain windows are handled explicitly

### Strategy comparison complete

This stage is complete when:

- multiple bounded strategy classes can be compared under the same truth model
- regime-aware evaluation is explicit
- research-only tools remain clearly advisory

### Paper runtime complete

This stage is complete when:

- source, feature, condition, policy, risk, execution intent, and settlement
  all have governed ownership
- continuous capture ownership is explicit
- realized feedback reaches the research layer without self-promotion

### Instrument expansion eligible

Perps and futures become eligible only when the earlier stages are already
stable and venue-specific assumptions have a governed home.

## Swarm completion versus product completion

`swarmState=terminal_complete` means:

- no eligible stories remain
- completion audits are clean
- no promotable follow-on work is pending

It does **not** automatically mean the full product north star is complete.

The swarm may reach terminal completion for one stage while the broader product
still has future-stage work parked intentionally.

## Non-goals for “complete”

These do not define completion by themselves:

- more model families
- more indicators
- more automation
- broader scope without explicit contracts
- shadow accuracy without governed paper outcomes
