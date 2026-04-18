# Memory, Hindsight, and Observer Hygiene

## Purpose

Track the durable memory-hygiene issues that currently block `Defi-engine`
from having a trustworthy project-scoped Hindsight bank and a clean path from
session exhaust to curated reusable project facts.

This file is stricter than a general note or handoff entry. It records the
specific defects that need to close before `project-defi-engine-v0.1` can be
treated as a reliable project-memory surface.

## Current Findings

| Finding | Why it matters | Current state | Close condition | Next action |
|------|------|------|------|------|
| `project-defi-engine-v0.1` was effectively unbootstrapped | durable project facts had nowhere clean to land, so session exhaust accumulated without a curated project bank | bank row was created explicitly, project-specific config/directive now exists, and a first reviewed seed set was inserted as `manual-seed` fallback rows because normal retain is degraded | reviewed seed facts exist, and the same facts are re-embedded or re-retained through the normal Hindsight path once the backend is healthy | keep a minimal reviewed promotion pass going instead of bulk-promoting from `codex-auto-Defi-engine`; replace the temporary `manual-seed` rows through the normal retain path when possible |
| `codex-auto-Defi-engine` is noisy and cross-project | raw recall exhaust is helpful for discovery, but unsafe as project truth because it mixes generic skill/session residue with repo-specific facts | bank is dense, contains many observation/world near-duplicates, and includes content that is not truly Defi-engine-specific | only durable repo facts are promoted out, and the auto bank remains a working-memory surface instead of a canon source | continue reviewed promotion into `project-defi-engine-v0.1`; do not treat auto-bank hits as canon without repo or observer verification |
| observer attribution initially looked missing because the first pass leaned too hard on session-state summaries | a false negative here would send cleanup work in the wrong direction and hide the real promotion bottleneck | `brain-observer-rs` does have a real Defi-engine lane under both `spool/defi-engine/` and `spool/_observer_state/normalized/defi-engine/`, with normalized events anchoring repo root `/home/netjer/Projects/AI-Frame/Brain/Defi-engine` in workspace `Brain` | observer and session-state surfaces agree on the same Defi-engine project lane, so future audits do not need to rediscover the mapping manually | keep using normalized observer evidence for reviewed promotion, and tighten the session-state visibility path so it does not imply the lane is missing |
| exact and near-duplicate directive cleanup was still incomplete across curated banks | duplicate directives increase maintenance noise and can hide which guidance is actually current | exact duplicates in `netjer-v0.1` and `codex-lessons-v0.1` are removed, and the near-duplicate `project-state` pair in `project-trading-engine-v0.1` has been collapsed to one directive | curated banks retain only materially distinct directives | keep duplicate-review lightweight and only remove rows that are exact or near-exact restatements |
| normal Hindsight retain is currently blocked by a degraded Ollama backend | without a healthy embed/generation backend, sync and async retain stall, queue churn grows, and project seeding falls back to manual maintenance | Hindsight API remains reachable, but Ollama generation/chat requests hang, async retains had to be canceled, and the initial Defi-engine seed set was inserted directly in Postgres as tagged fallback rows | Ollama-backed retain works again, async churn stops, and the temporary `manual-seed` rows are replaced or re-embedded through normal retain | restore the Ollama service first, then replay the reviewed seed set and lesson through the standard Hindsight path |

## Working Rules

- Treat `codex-auto-*` banks as working-memory recall exhaust, not project
  canon.
- Prefer small reviewed project-fact promotion over broad rebanking.
- Use repo truth and observer capture as evidence before promoting project
  facts.
- Keep reusable workflow lessons in `codex-lessons-v0.1`, not in the
  project-scoped bank.
- Treat `manual-seed` / `needs-reembed` rows as temporary receipts, not as a
  permanent substitute for normal retain.

## Close Condition

This issue can be considered closed when:

- `project-defi-engine-v0.1` is populated with a reviewed seed set of
  durable Defi-engine facts
- observer capture and session-state surfaces agree on the true Defi-engine
  project lane
- duplicate directives are removed from the affected curated banks
- the Ollama-backed retain path is healthy again, or the temporary
  `manual-seed` rows have been intentionally re-retained/re-embedded through a
  supported path
- the remaining `codex-auto-Defi-engine` content is clearly treated as
  working-memory exhaust instead of project canon

## Next Action

1. restore the Ollama service so normal Hindsight retain and reflect stop
   hanging
2. replay the reviewed Defi-engine seed set and workflow lesson through the
   standard retain path, replacing or re-embedding the temporary
   `manual-seed` rows
3. keep reviewed promotion flowing from repo truth and normalized observer
   evidence instead of from `codex-auto-Defi-engine`
