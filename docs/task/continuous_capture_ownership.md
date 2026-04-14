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
