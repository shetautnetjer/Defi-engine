# Autonomous Paper Practice Loop

This plan turns the existing historical ladder and live intraday paper-training
cycle into one repeatable autonomous paper-only practice system.

The loop is built on the current bounded primitives:

1. `d5 capture massive-minute-aggs --full-free-tier`
2. `d5 materialize-features global-regime-inputs-15m-v1`
3. `d5 run-shadow regime-model-compare-v1 --history-start ... --history-end ... --use-massive-context`
4. `d5 run-live-regime-cycle`
5. `d5 run-paper-cycle <quote_snapshot_id> --condition-run-id <id> --strategy-report <path>`

## Scope

The v1 loop stays inside paper-only authority:

- no live trading
- no wallet signing
- no YAML policy mutation
- no risk-gate code mutation
- no canonical strategy-registry mutation

Adaptive behavior is allowed only through the SQL-backed paper-practice profile
overlay.

## New runtime-owned practice commands

- `d5 run-paper-practice-bootstrap`
- `d5 run-paper-practice-loop`
- `d5 paper-practice-status`
- `d5 run-paper-close <session_key> --quote-snapshot-id <id> --reason <reason>`

All four commands should be usable from `codex exec` and other automation
wrappers through `--json`.

## Paper-practice overlay truth

The active profile overlay is stored in canonical SQL:

- `paper_practice_profile_v1`
- `paper_practice_profile_revision_v1`
- `paper_practice_loop_run_v1`
- `paper_practice_decision_v1`

This gives the loop one auditable place to change bounded paper behavior without
pretending that YAML or code has been re-authorized.

## Allowed profile mutation surface

Only these keys may change automatically in v1:

- `preferred_family`
- `strategy_report_path`
- `minimum_condition_confidence`
- `stop_loss_bps`
- `take_profit_bps`
- `time_stop_bars`
- `cooldown_bars`

Any wider patch must be rejected by proposal review.

## Loop order

Each practice iteration should:

1. run `run-live-regime-cycle`
2. read the latest paper-ready receipt
3. open at most one `SOL/USDC` paper session when regime, policy, risk, and the
   active profile all align
4. keep watching the open paper session with fresh Jupiter exit quotes
5. close automatically on:
   - stop loss
   - take profit
   - time stop
   - regime degradation to `risk_off` or `no_trade`
   - risk gate disallowing the position
6. review the closed result through the existing realized-feedback +
   proposal-review + proposal-comparison flow
7. apply an accepted profile patch only when it stays inside the allowed key
   set

## Current v1 defaults

- instrument: `SOL/USDC`
- context anchors: `BTC/USD`, `ETH/USD`
- cadence: `15m`
- long-only
- one open session max
- regime allowlist: `["long_friendly"]`
- minimum condition confidence: `0.60`
- stop loss: `100` bps
- take profit: `150` bps
- time stop: `16` bars
- cooldown: `4` bars

## Evidence and receipts

Each bootstrap, decision, profile revision, open trade, close trade, review,
and comparison must leave:

- SQL truth
- JSON artifact(s)
- `report.qmd`
- `artifact_reference`

Machine-visible loop state should stay in `.ai/dropbox/state/`:

- `paper_practice_status.json`
- `paper_practice_latest_trade_receipt.json`
- `paper_practice_latest_profile_revision.json`

## Relationship to the live regime cycle

`run-live-regime-cycle` remains non-trading and explicit. It is still the
capture/materialize/score/compare primitive. The autonomous paper-practice loop
is the only surface that may auto-open and auto-close paper sessions.

## Finish condition

This plan is successful when the engine can practice paper trading repeatedly,
review its closed outcomes, and adapt the active paper-only profile over time
without widening into live execution or mutating canonical policy/risk/code
surfaces.
