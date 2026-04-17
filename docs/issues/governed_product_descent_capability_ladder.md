# Governed Product Descent Capability Ladder

This issue is the durable planning guide for future Defi-engine work.

Use it as a repo-owned anchor when deciding what the swarm is descending toward,
what remains research-only, and what should be promoted into `prd.json` next.

## North Star

Defi-engine is not trying to become "a tmux swarm that edits a repo."

It is trying to become a governed self-improving engineering loop whose product
target is:

- a Solana-first backtesting and paper-trading application
- regime detection plus `up` / `down` / `flat` classification
- explicit strategy eligibility
- explicit paper settlement
- later Jupiter perps and Coinbase futures
- research tooling such as Chronos-2, Monte Carlo, Fibonacci, and
  autoresearch living in the research layer until they earn promotion into
  governed runtime owners

The swarm does not "keep looping until the final app exists."

The swarm descends the app through governed, auditable, receipt-backed
capability stages.

## Real Success Condition

The system is not succeeding because it has:

- more files
- more indicators
- more models
- more autonomous-looking behavior

The system is succeeding when it produces:

- profitable paper outcomes after fees and slippage assumptions
- bounded drawdown
- regime-aware correctness
- explicit instrument-aware eligibility
- explicit risk vetoes
- reproducible backtests
- auditable receipts for why a strategy was considered valid

## Capability Ladder

### Stage 1. Current truth consolidation

Finish the repo's current paper-runtime descent cleanly.

This is the current truth consolidation stage, not a later cleanup idea.

This stage includes:

- explicit completion contract
- clean terminal swarm state
- mailbox and lane-health surfaces that reflect real work rather than stale
  liveness
- writer-owned continuous docs sync for the entire `docs/` tree
- no contradictory claims about already-landed owners

### Stage 2. Backtesting truth layer

Before "great strategies," define the truth model for backtesting.

This backtesting truth layer has to be governed before later ML looks
meaningful.

This stage needs governed answers for:

- what is a tradeable instrument
- what is a bar, bucket, or event boundary
- what is a backtest session
- what fill, fee, slippage, and latency assumptions exist
- how spot, perps, and futures differ
- what counts as realized PnL in paper mode

### Stage 3. Regime and label truth

Define one canonical program for:

- `up`
- `down`
- `flat`
- trend persistence
- volatility regime
- liquidity regime
- macro regime
- invalid, uncertain, and low-confidence windows

### Stage 4. Strategy research layer

Now let research explore, but keep it advisory.

This is where:

- Chronos-2
- Monte Carlo
- Fibonacci feature families
- autoresearch
- ANN or relational ideas
- broader feature search
- bounded hypothesis generation

may live safely as evidence producers, candidate generators, and comparison
tools.

### Stage 5. Governed promotion ladder

Nothing becomes runtime authority because it is interesting.

The governed promotion ladder is what keeps research evidence from silently
becoming runtime truth.

Promotion requires:

- explicit contract
- deterministic inputs
- validation receipt
- documented failure modes
- rollback path
- bounded scope
- risk compatibility
- writer-integrator acceptance

### Stage 6. Instrument expansion

Only after spot backtesting and paper runtime are strong do we widen.

Preferred widening order:

1. Solana spot
2. Jupiter spot strategy depth
3. Jupiter perps
4. Coinbase futures

Each widening multiplies:

- slippage assumptions
- liquidation logic
- leverage risk
- session logic
- venue-specific behavior

## Research-Only By Default

These remain advisory until explicitly promoted:

- Chronos-2
- Monte Carlo
- Fibonacci-derived feature families
- autoresearch
- ANN and relationship modeling
- broad feature search and experiment generation

Research systems may propose, compare, and critique. They may not silently
become runtime authority.

## Swarm Roles

The swarm is not the trading engine itself. It is the governed maintainer and
descent mechanism for the repo.

### Research lane

- finds evidence
- tests bounded ideas
- compares challenger methods
- identifies gaps and weak assumptions

### Architecture lane

- decides which layer owns what
- decides what should be subtracted
- defines promotion prerequisites
- blocks research from leaking into runtime too early

### Builder lane

- implements bounded slices only
- adds tests and receipts
- does not auto-commit

### Writer-integrator lane

- accepts, rejects, blocks, or escalates
- updates `prd.json`
- appends `progress.txt`
- keeps the `docs/` tree current
- optionally creates governed commits after receipt-backed acceptance

## How To Judge "Better"

Define "better" using metrics such as:

- hit rate by regime
- precision and recall for `up` / `down` / `flat`
- calibration quality
- average return by signal bucket
- max drawdown
- risk-adjusted outcomes
- turnover sensitivity
- fee and slippage sensitivity
- out-of-sample robustness
- cross-instrument stability
- regime-transition robustness

Because a model can be directionally right and still be bad at making money.

## Next Backlog Themes

The next durable backlog themes should be:

1. continuous current-truth consolidation
2. commit governance in writer receipts
3. promotion-candidate artifact contract
4. backtest truth model
5. labeling program
6. strategy evaluation and challenger framework
7. execution intent before derivatives widening
8. only then bounded Chronos-2 and autoresearch follow-ons

## Practical Rule

When in doubt, phrase the swarm's job like this:

> Defi-engine descends through governed capability levels under explicit truth,
> tests, receipts, and promotion rules.

Do not phrase the job as:

> keep evolving until the full app exists.
