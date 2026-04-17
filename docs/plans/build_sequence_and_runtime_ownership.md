# Build Sequence and Runtime Ownership

## Purpose

Define the historical bridge between the original source-ingest bootstrap and
the target paper-first runtime so future task docs can see the old sequencing
without mistaking it for current repo truth.

This note synthesizes current repo docs, the local planning lane in `~/.openclaw/workspace-aya/defi-plans/`, and the workspace Notion page `Defi-engine`.

## Status

This note is historical context, not the current truth packet.

Use these surfaces for current planning truth instead:

- `docs/project/current_runtime_truth.md`
- `docs/prd/crypto_backtesting_mission.md`
- `docs/issues/governed_product_descent_capability_ladder.md`
- `docs/gaps/`

## Historical Truth

- the repo currently has real source capture, normalization, raw landing, canonical SQLite truth, DuckDB mirror sync, and operator CLI surfaces
- the repo did not yet have a runnable paper-trading engine when this note was
  authored, and `trajectory/`, `policy/`, `risk/`, and `settlement/` still
  remained placeholder surfaces at that time
- current docs already treat this honestly: the implemented surface is still foundation-stage ingest plus truth-building
- the missing planning gap is not "more explanation of ingest"; it is the build sequence that connects source truth to safe paper-session behavior

## End-To-End Runtime Descent

The intended runtime descent should remain explicit:

1. `source/`
   - capture provider payloads
   - record source health and provenance
   - keep raw-first receipts
2. canonical storage
   - land normalized truth in SQLite
   - mirror analysis-friendly state to DuckDB
   - preserve event-time authority in UTC
3. `features/`
   - materialize deterministic feature tables from canonical truth
   - define reusable feature contracts rather than ad hoc model inputs
4. `condition/`
   - score market, liquidity, and chain-state regimes from features
   - emit bounded condition outputs, not trade execution
5. `trajectory/`
   - provide advisory scenarios or forecasts only
   - never become a hidden execution authority
6. `policy/`
   - decide strategy eligibility, parameter surfaces, and decision traces
   - keep operator- and governance-sensitive rules explicit
7. `risk/`
   - apply hard vetoes, halts, and conservative overrides
   - remain final before any paper action is simulated
8. `settlement/`
   - own paper sessions, fill simulation, PnL, and reporting
   - turn approved policy decisions into auditable paper outcomes
9. `research_loop/`
   - compare realized paper outcomes against shadow alternatives
   - produce bounded improvement proposals without self-promoting them

## Build Sequence

The recommended implementation order should stay conservative:

1. finish source-precondition hardening already described in `docs/plans/source_expansion_preconditions.md`
2. define the continuous-capture ownership surface so ingest health, run cadence, and source completeness have an explicit runtime owner
3. make canonical truth tables sufficient for deterministic feature materialization instead of direct downstream provider coupling
4. create the first `features/` registry and feature-materialization contract
5. create the first `condition/` scorer contract using only canonical truth and features
6. add `policy/` decision traces so strategy eligibility is explainable before any paper execution exists
7. add `risk/` veto logic and halt surfaces before expanding paper-session behavior
8. add `settlement/` paper session state, fill assumptions, session metrics, and reporting
9. add `research_loop/` comparison and governed autoresearch only after paper-session receipts are stable

## Runtime Ownership Matrix

| Layer | Current state | Next authority to add | Notes |
|------|-------|-------|-------|
| `source/` | active | provider-role and source-completeness doctrine | current strongest owner in repo |
| canonical storage | active | event-table completeness review | already authoritative for truth landing |
| `features/` | partial | `condition/` handoff and policy-owned threshold governance | must not read providers directly |
| `condition/` | partial | bounded global regime scorer and condition receipts | should keep consuming features, not raw capture |
| `trajectory/` | scaffolded | advisory-only forecast contract | no runtime authority widening |
| `policy/` | accepted since superseded | strategy eligibility and decision-trace schema | see current runtime truth packet |
| `risk/` | accepted since superseded | veto matrix, halts, and safe defaults | see current runtime truth packet |
| `settlement/` | accepted since superseded | paper session ledger, fills, and reports | see current runtime truth packet |
| `research_loop/` | partial | shadow experiment ledger and artifact workflow | support only, never live authority |

## Documentation Descent

Future documentation should descend through these surfaces:

- `docs/project/`
  - current implemented repo reality
- `docs/plans/`
  - sequencing bridges like this note
- `docs/task/`
  - the current bounded slice for one owner or one seam
- `docs/issues/`
  - durable blockers and unresolved review findings
- `docs/gaps/`
  - known missing capability that should not be mistaken for shipped runtime

The first durable blocker set now lives in `docs/issues/paper_runtime_blockers.md`. Future runtime tasks should descend that file instead of rediscovering blockers in one-off notes.

## Immediate Follow-Ons

- turn the advisory semantic-regime YAML into the first `policy/` input instead of leaving bias mapping implicit in scorer semantics
- decide whether freshness thresholds stay code-local or move into explicit operator policy/config
- define the first `policy/` to `risk/` to `settlement/` trace path before adding any paper-session loop

## Not Yet Safe To Claim

The repo described by this historical note should not be described as:

- a finished paper-trading engine
- a live-trading system
- an engine with implemented strategy selection, risk gating, settlement, or autoresearch governance

The current repo has moved beyond this historical state. Use the current
runtime-truth packet and the governed product-descent issue guide for active
planning.
