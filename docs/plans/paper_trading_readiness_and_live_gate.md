# Paper Trading Readiness And Live Gate

This plan makes the near-term product target explicit:

- build a Solana-first paper-trading app that can keep replaying, scoring, and
  documenting its behavior honestly
- keep runtime authority bounded while label and strategy research harden
- treat any future live-trading widening as a separate governed gate

The repo should optimize for credible paper trading first, not for early live
execution.

The next concrete implementation descent for that paper-first target is tracked
in [Autonomous Paper Practice Loop](autonomous_paper_practice_loop.md).

## Current truthful base

Already real in repo truth:

- canonical source truth in SQLite
- bounded feature materialization
- bounded condition scoring
- explicit policy tracing
- hard risk gating
- explicit execution intent
- explicit quote-backed paper settlement
- explicit spot-first backtest replay truth
- advisory shadow evaluation plus realized-feedback comparison
- bounded label-program and strategy-eval research loops
- bounded regime-model comparison on canonical 15-minute truth
- bounded live intraday regime cycle with paper-ready receipts

The current paper-runtime and backtest foundation is strong enough that the
remaining work is no longer “basic trading engine plumbing.” The remaining work
is governed selection:

- which label program is canonical
- which strategy families are eligible in which regimes
- when paper behavior is trustworthy enough to count as an app, not just a
  research stack

## Near-term finish line

The next meaningful finish line is:

`Defi-engine` can run a repeatable Solana spot paper-trading loop where
accepted labels and accepted strategy families select bounded paper actions,
results are recorded in SQL truth, and QMD evidence accumulates with UTC
timestamps for replay and audit.

That requires more than “good models.” It requires:

- canonical label truth
- governed strategy comparison
- repeated paper/backtest evaluation under explicit fee and slippage
  assumptions
- durable UTC-dated QMD reports
- evidence-rich receipts before any runtime widening

## Regime dependency note

For the bounded regime owner that sits underneath `LABEL-001`, the current
honest dependency posture is:

- current runtime-adjacent surface:
  [`hmmlearn` tutorial](https://hmmlearn.readthedocs.io/en/latest/tutorial.html)
- current maintenance caveat:
  [`hmmlearn` README](https://github.com/hmmlearn/hmmlearn/blob/main/README.rst)
- strongest next comparison candidate:
  [`statsmodels` Markov switching dynamic regression models](https://www.statsmodels.org/dev/examples/notebooks/generated/markov_regression.html)
- broader research-only alternative:
  [`pomegranate` Hidden Markov Models tutorial](https://pomegranate.readthedocs.io/en/latest/tutorials/B_Model_Tutorial_4_Hidden_Markov_Models.html)

Until a later shadow-only comparison says otherwise:

- keep the current `hmmlearn` plus GMM fallback posture
- do not imply that modern scikit-learn already provides the regime HMM owner
- do not widen runtime authority just because a better-matched model family may
  exist
- evaluate `statsmodels` in shadow before any runtime dependency swap
- use `d5 run-shadow regime-model-compare-v1` as the bounded comparison seam
  for that evaluation, and keep it advisory-only rather than a runtime-owner swap

## Build order from here

### 1. Finish `LABEL-001` against real repo data

The implementation surface exists, but the live repo still needs the successful
feature-run inputs needed to execute the bounded label loop on real data.

Done when:

- `d5 run-label-program canonical-direction-v1` can run against
  the real repo state, not just test fixtures
- the resulting QMD and JSON artifacts are durable and auditable
- the repo can prove which label family is currently canonical

### 2. Finish `STRAT-001` as governed strategy selection

The implementation surface also exists, but the paper-trading app is not ready
until strategy-family comparison is accepted as a stable advisory selector.

Done when:

- the named strategy families are actually scored on real repo truth
- challenger outputs are compared by governed metrics
- the current advisory baseline is clear enough to feed paper-trading
  decisions without becoming hidden runtime authority

### 3. Add a bounded paper-trading operator loop

The runtime now has a first controlled operator loop that:

- reads the latest advisory strategy selector output
- keeps mint choice explicit through quote provenance instead of hidden
  inference
- builds bounded paper intents
- settles those intents in the paper ledger
- emits UTC-dated QMD evidence alongside SQL truth

This loop remains paper-only and spot-first.

The remaining readiness work is real-data depth and selection quality:

- condition scoring still needs enough 15-minute history to run on live repo
  truth without threshold weakening
- label and strategy outputs still need sustained real-data evidence before the
  paper loop can be described as routinely operator-ready
- the historical ladder should now use the bounded Massive free-tier minute
  window first, then append live Jupiter/Helius/Coinbase context intraday
- the paper operator should keep using explicit paper-ready receipts rather than
  hidden auto-execution

### 4. Keep documenting evidence in QMD and SQL

QMD should carry:

- UTC run date and time
- important thresholds and assumptions
- label/strategy conclusions
- comparison notes
- open risks

SQL should carry:

- source truth
- paper truth
- backtest truth
- experiment metrics
- realized-feedback comparisons

This keeps historical accuracy and future replay integrity separate from
narrative evidence.

### 5. Treat live trading as a future governed gate

Future live trading is blocked on more than win ratio.

An 80% win ratio alone is not enough because it does not answer:

- fee and slippage robustness
- drawdown behavior
- calibration quality
- turnover sensitivity
- out-of-sample stability
- regime transition stability
- operational key safety
- failure-mode containment

The future live gate must require all of the following:

- explicit widening out of paper-only scope
- a documented private-key/operator-control model
- stronger readiness metrics than headline win rate
- explicit live risk controls and halt behavior
- writer-backed acceptance of the widening gate

Until then:

- no live wallet signing
- no live order routing
- no automatic key use in runtime

## Practical rule

If a change makes the repo better at:

- replaying reality
- selecting bounded paper actions
- measuring outcomes honestly
- documenting results in UTC-dated QMD

then it is moving toward the app.

If a change tries to jump directly from advisory research to live authority,
it is widening too early.
