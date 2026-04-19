# Trading QMD Report Contract

## Purpose

Trading-facing runs in this repo should emit one durable evidence packet shape:

- `config.json`
- `summary.json`
- `report.qmd`

`SQL` remains canonical truth.
`QMD` remains the human-and-LLM evidence packet.
Thin `JSON` sidecars remain the machine routing surface only.

## Storage Contract

The historical market-data warehouse is intentionally split:

- raw source artifacts stay as `CSV.gz`
- deep-history and replay reads use partitioned `Parquet`
- canonical normalized/runtime truth stays in `SQL`

Never store raw CSV blobs inside SQL columns.

## Required QMD Frontmatter

Every trading-facing `report.qmd` should carry small YAML frontmatter with these fields when available:

- `title`
- `date`
- `format`
- `report_kind`
- `run_id`
- `owner_type`
- `owner_key`
- `profile_revision_id`
- `selected_research_profile`
- `instrument_scope`
- `context_instruments`
- `timeframe`
- `summary_path`
- `config_path`

Do not add a separate report YAML sidecar unless a future operator workflow proves it is necessary.

## Required Sections

Trading-facing QMDs should follow this section order whenever the surface applies:

1. `Summary`
2. `Market / Source Context`
3. `Regime / Condition / Policy / Risk`
4. `Strategy / Profile`
5. `Trade / Replay Outcome`
6. `Failure Attribution`
7. `Bounded Next Change`
8. `Artifact / SQL References`

The sections may be omitted only when they are truly not relevant to the report kind.

## Minimum Content Expectations

### Market / Source Context

- source set actually used
- cache completeness or freshness
- OHLCV / L2 / trades availability when relevant
- context-only futures/perps note when relevant
- data gaps or stale-data notes

### Regime / Condition / Policy / Risk

- semantic regime
- condition run id
- policy state
- risk state
- veto or reason codes
- whether the selected strategy was regime-aligned

### Strategy / Profile

- active profile revision
- selected research profile
- preferred strategy family
- strategy report path
- confidence threshold
- stop / take-profit / cooldown / time-stop settings
- delta from the previous active revision when relevant

### Trade / Replay Outcome

- entry/exit timestamps
- entry/exit prices or mark assumptions
- realized PnL
- close reason
- fee/slippage assumptions when relevant

### Failure Attribution

Classify the weakest surface using one of:

- `data coverage`
- `feature issue`
- `regime/condition issue`
- `strategy mismatch`
- `policy issue`
- `risk issue`
- `execution/settlement assumption issue`
- `no-trade was correct`
- `inconclusive / sample too small`

### Bounded Next Change

Every trading-facing report must end with one explicit bounded action:

- `keep`
- `revert`
- `shadow`
- one bounded proposal candidate

The report should never imply scope widening by itself.

## Official References

- Massive Flat Files Quickstart: https://massive.com/docs/flat-files/quickstart
- Massive crypto flat files overview: https://massive.com/docs/flat-files/crypto/overview
- Massive crypto minute aggregates dataset: https://massive.com/docs/flat-files/crypto/minute-aggregates
- OpenAI Codex changelog: https://developers.openai.com/codex/changelog

## Operator Notes

- Keep the repo private once the training and trading automation lane is ready for wider unattended use.
- Append a Plane B journal entry after major reporting/storage contract changes so the chronology stays readable without becoming runtime authority.
