# Repo Understanding Snapshot — 2026-04-17

## Purpose

Capture a durable understanding pass over the repo using:

- `graphify-local`
- `gitnexus-local`
- `socraticode-local`

The goal was not just to map the codebase, but to see whether the current
script sprawl is a real source of confusion.

## What The Tools Agree On

All three tools are materially better at understanding the Python trading
engine than the shell swarm/orchestration layer.

The clearest shared engine spine is:

- `src/d5_trading_engine/capture/runner.py`
- `src/d5_trading_engine/storage/truth/models.py`
- `src/d5_trading_engine/features/materializer.py`
- `src/d5_trading_engine/condition/scorer.py`
- `src/d5_trading_engine/policy/global_regime_v1.py`
- `src/d5_trading_engine/risk/gate.py`
- `src/d5_trading_engine/settlement/paper.py`
- `src/d5_trading_engine/research_loop/shadow_runner.py`
- `src/d5_trading_engine/research_loop/realized_feedback.py`

This means the paper-first runtime and research engine are now legible as a
bounded layered system.

## What The Tools Do Not Agree On Cleanly

The orchestration layer is much less coherent.

Cross-tool comparison plus shell corroboration show the swarm control plane is
spread across too many files that all influence related concepts:

- `scripts/agents/swarm_state.py`
- `scripts/agents/run_persistent_cycle.sh`
- `scripts/agents/sync_swarm_state.sh`
- `scripts/agents/send_swarm.sh`
- `scripts/agents/health_swarm.sh`
- `scripts/agents/status_swarm.sh`
- `scripts/agents/promote_gap_story.sh`
- `scripts/agents/update_story_state.sh`
- `scripts/agents/write_acceptance_receipt.sh`
- `scripts/agents/write_story_promotion_receipt.sh`
- `prd.json`

This is the actual likely source of “nothing new has landed” / “it still feels
stalled”:

- the engine is relatively coherent
- the story-selection and writer-promotion control plane is not yet narrow
  enough

## Critical Reading

The repo currently has two different kinds of logic:

### 1. Engine Logic

This is mostly healthy and layered.

- source capture
- deterministic features
- regime scoring
- policy
- risk veto
- paper settlement
- shadow evaluation

### 2. Swarm Governance Logic

This is where authority overlaps.

Observed overlaps:

- `swarm_state.py` manages trigger queueing and trigger clearing
- `run_persistent_cycle.sh` decides when to launch lanes and when to wait
- `sync_swarm_state.sh` mutates `activeStoryId`, `swarmState`, and
  `completionAuditState`
- `promote_gap_story.sh` and `update_story_state.sh` both write `prd.json`
  and can set `activeStoryId`
- `health_swarm.sh` and `status_swarm.sh` derive truth again from the same
  surfaces, which is useful for reporting but can obscure which script is
  truly authoritative
- `send_swarm.sh` still carries some mode inference on top of caller intent

This is enough overlap to make the system feel like it is moving while it is
actually spending time resolving its own control-plane ambiguity.

## Tool-Specific Verdicts

### Graphify

Best at:

- corpus-level structure
- engine hubs
- major Python runtime surfaces

Weak at:

- shell orchestration
- script-level “who actually owns this state change?” questions

### GitNexus

Best at:

- confirming index freshness and overall graph scale

Weak at:

- shell orchestration symbol grounding
- targeted questions around `sync_swarm_state` / `run_persistent_cycle`

### SocratiCode

Best at:

- proving infrastructure health
- lightweight graph build

Weak at:

- reliable shell-level search in this repo on this pass
- useful dependency output for `scripts/agents/run_persistent_cycle.sh`

## Recommended Narrowing

The next cleanup should not widen the system. It should narrow the control
plane.

### Recommended target shape

1. `sync_swarm_state.sh`
   - sole owner of:
     - `activeStoryId`
     - `swarmState`
     - `completionAuditState`

2. `run_persistent_cycle.sh`
   - scheduler only
   - launches or waits
   - does not own durable story promotion

3. `swarm_state.py`
   - sole owner of transient trigger queue semantics
   - no duplicate durable story activation logic

4. `promote_gap_story.sh` and `update_story_state.sh`
   - review for consolidation
   - ideally one canonical path mutates `prd.json` story state

5. `health_swarm.sh` and `status_swarm.sh`
   - reporting only
   - no hidden state mutation

6. `send_swarm.sh`
   - prompt/marker dispatch only
   - minimal mode inference

## Practical Next Step

Before adding more swarm features, do a bounded orchestration narrowing pass:

- identify which script is authoritative for each state mutation
- remove duplicated `prd.json` mutation paths where possible
- leave the engine logic alone
- make the shell control plane smaller and more obvious

## Raw Artifacts

Raw outputs for this snapshot are stored under:

- `.ai/dropbox/state/repo_understanding/2026-04-17/`

The compact comparison table is:

- `.ai/dropbox/state/repo_understanding/2026-04-17/repo_understanding_tools.csv`
