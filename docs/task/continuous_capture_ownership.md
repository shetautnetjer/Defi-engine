# Continuous Capture Ownership

Active execution surface for promoting ingest from a truthful bootstrap capture runner into a runtime freshness and completeness owner that downstream layers can safely depend on.

## Goal

Make continuous and recurring capture behavior explicit enough that later `features/`, `condition/`, and `policy/` work can depend on source freshness without reaching back into provider-specific assumptions.

## Current Truth

- `CaptureRunner` already owns `ingest_run` lifecycle, raw receipt writing, normalization dispatch, and `source_health_event` logging
- the canonical schema already has `ingest_run`, `source_health_event`, and `capture_cursor`
- `d5 status` can show recent ingest runs and the latest health event per provider
- the repo still does not define which capture lanes are expected to be continuously fresh, how stale state is recognized, or what operator-visible response should happen when a source falls behind

## This Slice Covers

- classifying active capture lanes by runtime expectation:
  - interval or recurring capture
  - bounded stream receipt lane
  - discovery or backfill lane
  - operator-invoked research lane
  - readiness-only lane
- defining which existing truth surfaces are authoritative for freshness and completeness:
  - `ingest_run`
  - `source_health_event`
  - `capture_cursor` where resumable capture is real
- defining stale, missing, and degraded-source semantics for the active providers without widening into live-trading logic
- deciding what `d5 status` must eventually expose so source ownership becomes operator-visible instead of implied
- recording which providers are eligible to become downstream dependencies and which remain bounded or readiness-only

## Exit Criteria

- every active capture flow is mapped to a runtime expectation class
- the repo has an explicit freshness and completeness rule for each active provider family:
  - Jupiter
  - Helius
  - Coinbase
  - FRED
  - Massive
- the task names which truth tables or events define freshness for each lane
- the task names what counts as:
  - never started
  - healthy and recent
  - degraded
  - stale
  - readiness-only
- the task defines the minimum operator-visible output required from `status` or a future `doctor` surface
- the docs updated by this slice point back to `docs/issues/paper_runtime_blockers.md` and `docs/plans/source_map_and_source_completeness.md`

## Initial Lane Reading

- Jupiter prices and quotes
  - strongest current candidate for recurring freshness ownership
- Helius discovery and enhanced transactions
  - useful for discovery and bounded chain-state truth, but freshness rules must distinguish discovery/backfill from steady-state monitoring
- Helius websocket events
  - bounded raw stream receipt lane only; not yet a canonical runtime event surface
- Coinbase products, candles, trades, and book snapshots
  - recurring market-data lane, but still not an execution authority
- FRED series and observations
  - slower macro lane with different freshness expectations than market data
- Massive
  - readiness-only until entitlement and payload proof exist

## Initial Freshness Matrix Draft

This draft names the current lane reading without locking the repo into numeric windows yet. The implementation slice should convert these into explicit freshness thresholds.

| `capture_type` | Runtime expectation class | Authoritative signal now | Provisional stale reading |
|------|-------|-------|-------|
| `jupiter-tokens` | operator-invoked reference refresh | latest successful `ingest_run` plus latest `source_health_event` | stale when no successful baseline exists for the current tracked universe or provider contract |
| `jupiter-prices` | recurring market snapshot | latest successful `ingest_run` plus latest `source_health_event` | stale when the lane stops succeeding within its chosen operating cadence |
| `jupiter-quotes` | recurring market snapshot | latest successful `ingest_run` plus latest `source_health_event` | stale when quote capture falls behind its chosen operating cadence |
| `helius-transactions` | recurring chain-state pull | latest successful `ingest_run` plus latest `source_health_event` | stale when tracked addresses are configured but transaction capture does not refresh within its chosen cadence |
| `helius-discovery` | discovery and backfill lane | latest successful `ingest_run` plus registry-side effects | stale when tracked-address or program-discovery refresh is required but the lane has not been rerun |
| `helius-ws-events` | bounded raw stream receipt lane | latest successful `ingest_run`, latest `source_health_event`, and recent raw notification receipts | stale when the stream is expected to be active but raw receipts stop appearing within the stream freshness window |
| `coinbase-products` | low-frequency reference refresh | latest successful `ingest_run` plus latest `source_health_event` | stale when venue metadata is relied on downstream but has not been refreshed within its chosen cadence |
| `coinbase-candles` | recurring market-data lane | latest successful `ingest_run` plus latest `source_health_event` | stale when candle capture falls behind its chosen cadence |
| `coinbase-market-trades` | recurring market-data lane | latest successful `ingest_run` plus latest `source_health_event` | stale when trade-event capture falls behind its chosen cadence |
| `coinbase-book` | recurring market-data lane | latest successful `ingest_run` plus latest `source_health_event` | stale when book snapshot capture falls behind its chosen cadence |
| `fred-series` | operator-invoked reference metadata refresh | latest successful `ingest_run` plus latest `source_health_event` | stale when macro metadata needs refresh and no successful baseline exists |
| `fred-observations` | slower recurring macro lane | latest successful `ingest_run` plus latest `source_health_event` | stale when macro observations fall behind their chosen low-frequency cadence |
| `massive-crypto` | readiness-only lane | explicit success or fail-closed receipt | never blocks downstream freshness until Massive is promoted beyond readiness-only |

## Cursor Reality

- `capture_cursor` exists in canonical schema as a reserved resumability surface
- the repo does not yet have a strong current claim that any active capture lane is freshness-authoritative through cursor progression alone
- this slice should only use cursor state where resumable semantics are actually real, rather than implying resumability across the whole ingest stack

## Freshness State Model

Every non-readiness lane should eventually resolve to one of these operator-visible states:

- `never_started`
  - no successful baseline receipt exists for the lane
- `healthy_recent`
  - the most recent successful run is still within the lane freshness window and the latest health signal is not failed
- `degraded`
  - the lane still has a recent successful baseline, but the latest health signal failed or the lane is nearing staleness
- `stale`
  - the lane is past its freshness window for downstream dependence
- `readiness_only`
  - the lane is intentionally excluded from runtime freshness gating

Interpretation rules:

- `never_started` blocks downstream dependence for every lane except explicit readiness-only probes
- `degraded` should not silently fail open into downstream runtime decisions
- `stale` means the lane may still contain useful historical truth, but it is no longer safe to treat it as current runtime context
- `readiness_only` is for surfaces like current Massive capture where success or failure is informative but not freshness-authoritative

## Minimum Status Surface

The current `d5 status` command already shows recent `ingest_run` rows and latest provider health. This slice should define the minimum additional information required to make runtime ownership real without yet implementing a full `doctor` command.

Minimum per-lane output:

| Field | Why it matters |
|------|-------|
| `provider` | anchors the source family |
| `capture_type` | makes freshness specific to the actual lane, not just the provider |
| `expectation_class` | distinguishes recurring, discovery, stream, and readiness-only lanes |
| `last_success_at_utc` | tells downstream consumers when the lane last produced a valid baseline |
| `last_failure_at_utc` | keeps recent breakage visible instead of hidden behind an older success |
| `latest_health_at_utc` | ties freshness to the most recent provider-health signal |
| `freshness_state` | exposes `never_started`, `healthy_recent`, `degraded`, `stale`, or `readiness_only` directly |
| `downstream_eligible` | answers whether later runtime layers may currently depend on this lane |
| `latest_error_summary` | keeps operator triage close to the freshness state |

Recommended derived rules:

- `downstream_eligible = false` for `never_started`, `stale`, and `readiness_only`
- `downstream_eligible = false` for `degraded` unless a later policy explicitly allows soft dependence
- `downstream_eligible = true` only for lanes in `healthy_recent`

## Threshold Strategy

This repo should not guess numeric freshness windows directly from provider request spacing.

Instead:

- request throttles such as `JUPITER_MIN_REQUEST_INTERVAL_SECONDS = 2.0` protect the adapter, but do not define the runtime freshness window by themselves
- bounded stream controls such as `HELIUS_WS_MAX_MESSAGES` define capture limits, but do not by themselves define a healthy stream cadence
- the first implementation should assign freshness windows by expectation class and lane role, then make those thresholds explicit in config or operator policy

Initial threshold guidance:

- recurring market-data lanes
  - need explicit freshness windows because they are the strongest candidates for downstream feature dependence
- discovery and backfill lanes
  - should be freshness-qualified only when a known refresh requirement exists
- slower macro lanes
  - should use a separate low-frequency freshness policy from market-data lanes
- readiness-only lanes
  - should remain outside freshness gating until promoted

## Deferred On Purpose

- scheduler choice such as cron, systemd, Docker, or external orchestration
- durable resumability beyond the current `capture_cursor` reality
- richer Helius protocol-aware decoding
- feature materialization itself
- condition, policy, risk, settlement, or research-loop implementation
- live trading, wallet automation, or promotion-sensitive runtime behavior

## Next Actions After This Slice

1. refine the provisional freshness matrix into explicit thresholds and operator-visible stale-state rules
2. decide whether `status` is enough for operator visibility or whether `doctor` becomes necessary for stale-state reporting
3. define the first downstream dependency contract for `features/` so it can consume only freshness-qualified canonical truth
