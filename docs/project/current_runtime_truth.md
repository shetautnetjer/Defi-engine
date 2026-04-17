# Current Runtime Truth

This file is the compact runtime-truth packet for the Defi-engine swarm.

Read it before widening backlog truth or claiming a runtime owner is still
missing.

## Real now

The repo already owns these runtime-adjacent surfaces:

- source truth in canonical SQLite plus provider-backed capture receipts
- explicit capture freshness ownership
- bounded deterministic feature materialization
- bounded condition scoring
- explicit policy tracing
- explicit hard risk gating
- explicit paper settlement and paper reporting
- bounded shadow evaluation
- advisory realized-feedback comparison between shadow and paper outcomes

Current concrete surfaces include:

- `spot_chain_macro_v1`
- `global_regime_inputs_15m_v1`
- `global_regime_v1`
- `policy_global_regime_trace_v1`
- `risk_global_regime_gate_v1`
- `paper_session`
- `paper_fill`
- `paper_position`
- `paper_session_report`
- `experiment_realized_feedback_v1`
- `intraday_meta_stack_v1`

## Still missing

The remaining runtime owner gap is:

- explicit execution intent between `risk/` and `settlement/`

That gap is about instrument, side, size, and entry-exit intent. It is not a
reason to reopen policy, risk, or settlement as if those layers were absent.

## Research-only by default

These remain advisory unless promoted through the runtime authority ladder:

- Chronos-2
- Monte Carlo
- Fibonacci-derived feature families
- autoresearch
- ANN / relationship modeling
- finder audits
- shadow model outputs

They may propose, compare, or critique. They may not silently become runtime
authority.

## Swarm truth rule

Canonical swarm truth still lives in:

- `prd.json`
- `progress.txt`
- accepted docs

The `.ai/dropbox/` tree is an exchange surface. The `.ai/swarm/*.yaml` layer is
a machine-readable governance packet, not a live runtime source of truth in v1.
