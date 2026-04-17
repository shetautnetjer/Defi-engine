# Label Program And Regime Taxonomy Gap

## Stage

Stage 3: regime and label truth.

## Current truth

The repo already has:

- `global_regime_v1`
- one bounded regime scorer
- semantic regime labels such as `long_friendly`, `short_friendly`,
  `risk_off`, and `no_trade`
- bounded shadow labels such as `tb_60m_atr1x` and `tb_240m_atr1x`

## Gap

The repo still lacks one canonical labeling program that defines:

- `up`
- `down`
- `flat`
- trend persistence
- volatility regime
- liquidity regime
- macro regime
- invalid, uncertain, and low-confidence windows

## Why it matters

Without one authoritative label and regime taxonomy, later strategy comparison
and promotion logic will drift between docs, experiments, and runtime
assumptions.

## Close when

- the repo has one canonical label taxonomy with horizon rules
- regime dimensions are defined explicitly rather than implied by one scorer
- confidence, invalid, and low-signal windows are part of the contract
- the evaluation metrics used for label quality are documented and tested
