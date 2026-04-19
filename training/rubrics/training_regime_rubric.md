# Training Regime Rubric

This rubric mirrors the strong staged eval from the companion Notion page and
adapts it to the current D5 engine. It is the training lane's repo-owned
reference for how a candidate should be judged.

## How To Use It

- Every proposal should declare exactly one changed surface.
- A candidate must pass hard gates before it is compared on weighted score.
- Paper evidence outranks offline-only evidence when proposals compete.
- The reviewer should record both the stage result and the failure attribution.

## Changed Surface Options

- feature set
- condition model
- regime semantic map
- strategy policy
- risk rule
- execution or fill model
- report or diagnostic layer

## Hard Gates

The candidate does not advance if any of these fail:

- truth and replay integrity
- leakage check
- reproducibility
- risk safety floor
- minimum paper evidence when competing with already paper-proven ideas

## Stage 0: Truth And Replay Integrity

Pass or fail.

Check:

- no lookahead leakage
- raw to normalized replay works
- source freshness is acceptable
- null and missing rates stay within tolerance
- joins are stable
- run is reproducible

## Stage 1: Condition Quality

Judge usefulness, not generic classification accuracy.

Good metrics:

- dwell time or median state duration
- flip rate per day or session
- out-of-sample state occupancy stability
- transition plausibility
- confidence collapse or stale-input failure rate

## Stage 2: Regime Usefulness

A regime is good if it changes downstream decisions and outcomes in a useful,
stable way.

Good metrics:

- regime-conditioned expectancy separation
- regime-conditioned future volatility or trend dispersion
- no-trade purity
- regime-specific strategy dispersion
- semantic stability across windows

## Stage 3: Strategy-Policy Fit

Judge whether policy chooses the right action inside the detected regime.

Good metrics:

- uplift versus one static baseline strategy
- regret versus ex-post best strategy in that regime
- no-trade decision quality
- policy stability across windows
- coverage versus precision of selected strategies

## Stage 4: Risk Correctness

Risk is about improving the distribution without breaking the system.

Good metrics:

- max drawdown reduction
- expected shortfall or tail-loss reduction
- veto precision on bad trades
- cost of false vetoes
- exposure-limit violations equal zero
- stale-feed and anomaly blocks behave as designed

## Stage 5: Paper-Cycle Evidence

This stage outranks earlier offline-only stages when proposals compete.

Good metrics:

- realized paper PnL
- max drawdown
- turnover
- fill ratio
- modeled versus realized slippage gap
- session stability
- anomaly-halt and stale-feed-halt behavior
- number of cleanly reconstructed decisions

## Stage 6: Automation And Governance Quality

Good metrics:

- one-change-only isolation respected
- rollback path exists
- QMD report exists
- SQL metrics exist
- artifact references resolve
- runtime failures introduced equal zero

## Weighted Score

After the hard gates pass, use a score out of 100:

- truth and replay integrity: 15
- condition quality: 15
- regime usefulness: 20
- strategy-policy fit: 20
- risk correctness: 15
- paper-cycle evidence: 10
- automation and governance quality: 5

This keeps raw PnL from dominating and forces structural correctness to matter.

## Failure Attribution Matrix

After every run, answer:

- condition failure
- regime mapping failure
- strategy-policy failure
- risk failure
- execution or fill failure
- data truth failure

The chosen attribution should drive the next bounded experiment.

## Diagnostic Lenses

These models help locate where a fix belongs, not silently rewrite the engine:

- XGBoost for nonlinear structured diagnostics and feature-attribution reviews
- Random Forest for stable baseline comparison and robustness checks
- Isolation Forest for anomaly overlap and bad-tape detection

Treat them as evidence tools unless a separate promotion path approves more.
