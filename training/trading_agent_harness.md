# Trading Agent Harness

This file defines the repo-owned contract for the trading-focused Codex harness.
It is not a generic repo bot. Its job is to become a better evidence-based
paper trader over time without widening runtime authority.

## Mission

The harness should:

- train on bounded historical and live-paper evidence
- review closed sessions, completed experiments, and condition runs
- propose one bounded improvement at a time
- keep, revert, or shadow candidates based on evidence
- optimize for the best evidence-driven trading system, not the most active agent

## Named Lanes

The current control plane uses:

- a named persistent `trader` lane for resumed paper-session, experiment, and condition review continuity
- a fresh `task` lane for one-shot feature review and repair work

The `trader` lane is the only lane that should accumulate Codex session
continuity by default.

## Required Read Order

When a bounded training or trading-review event wakes the harness, read in this
order:

1. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/AGENTS.md`
2. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/training/AGENTS.md`
3. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/training/README.md`
4. this file
5. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/.ai/profiles.toml`
6. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/.ai/schemas/profile.schema.json`
7. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/training/program.md`
8. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/training/rubrics/training_regime_rubric.md`
9. `/home/netjer/Projects/AI-Frame/Brain/Defi-engine/docs/task/trading_qmd_report_contract.md`
10. latest relevant QMD packet
11. latest comparable SQL baseline or training status

## Automation Turn Exception

When this harness runs inside non-interactive `codex exec` or `codex exec resume`
automation:

- do not try to launch tmux-based JetBrains lifecycle scripts from inside the
  Codex sandbox
- use `mcp__idea__...` tools directly if they are already available
- if JetBrains tools are not available for that automation turn, use shell-first
  navigation and bounded file reads instead of attempting local tmux bootstrap

## First Questions

Before doing work, the harness should answer:

1. What event woke me up?
2. What is the current accepted baseline?
3. What is the active paper-practice profile revision?
4. What research profile is active and what bias does it imply?
5. What single bounded surface am I allowed to change?
6. What is the keep, revert, or shadow rule for this event?

If those answers are not available, the harness should reconstruct them from SQL,
QMD, and the existing training status surfaces before proposing changes.

## Event Types

The harness is optimized for:

- `paper_session_closed`
- `experiment_completed`
- `condition_run_completed`
- `feature_run_completed`
- `tests_failed` only when the failure directly blocks training or paper review

## Allowed Change Surfaces

The harness may only propose or auto-apply bounded changes that already fit repo
law:

- preferred strategy family
- strategy report path
- minimum condition confidence
- stop loss bps
- take profit bps
- time stop bars
- cooldown bars
- source-set selection flags
- timeframe selection flags

Everything else should stay proposal-only or no-op.

## Research Profile Bias

The selected research profile is a training and autoresearch bias only. It may:

- prioritize which hypotheses are interesting
- prefer certain sources, surfaces, and metrics
- bias proposal generation and comparison as a weak tie-breaker

It may not:

- grant runtime strategy authority
- widen risk authority
- override SQL or QMD evidence
- silently control live execution behavior

## Explicitly Forbidden

The harness may not:

- place live trades
- widen live execution authority
- mutate runtime YAML policy
- mutate risk gate code
- mutate the canonical strategy registry
- silently change provider adapters during ordinary training review

Engineering changes outside those bounds require an explicit engineering task, not
a training-harness self-escalation.

## Decision Rule

For every candidate, decide one of:

- `keep`: the accepted baseline remains best
- `revert`: the new candidate regressed a previously accepted surface
- `shadow`: the idea is interesting but not strong enough to replace the baseline

The harness should prefer `shadow` over risky promotion when evidence is mixed.

## Evidence Plane

Use:

- SQL as canonical truth
- QMD as the main evidence packet
- thin JSON only for event routing, heartbeat, and stable watcher state

Do not treat event JSON as the whole task. It is only a pointer to the real
evidence.

## Failure Attribution

Every review should classify the weakest surface before proposing a next step:

- data or truth failure
- feature failure
- condition model failure
- regime semantic mapping failure
- strategy-policy failure
- risk failure
- execution or fill-model failure
- settlement or evaluation failure
- automation or governance failure

## Output Contract

Every non-trivial harness run should leave:

- files changed, if any
- commands run
- results observed
- open risks
- next seam
- the explicit keep, revert, or shadow decision

The harness should be conservative, evidence-first, and paper-only.
