## Structural Workflow Default
- For runtime seams, capture layout, packet/export changes, refactors, and
  multi-file implementation work, prefer `$jetbrains-skill` and
  `$jetbrains-mcp` before broad shell search.
- Start or switch the headless JetBrains session first:
  - `~/.config/agents/skills/jetbrains-mcp/scripts/mcp_start_headless.sh /home/netjer/Projects/AI-Frame/Brain/Defi-engine`
  - `~/.config/agents/skills/jetbrains-mcp/scripts/mcp_status.sh /home/netjer/Projects/AI-Frame/Brain/Defi-engine`
- Prove the IDE bridge is live with:
  1. `mcp__idea__get_project_modules`
  2. `mcp__idea__get_repositories`
  3. `mcp__idea__list_directory_tree`
- Exception for non-interactive automation turns:
  - when running inside `codex exec` or `codex exec resume`, do not try to
    launch the tmux-based JetBrains lifecycle scripts from inside the sandbox
  - use already-available `mcp__idea__...` tools directly when present
  - if JetBrains tools are unavailable in that sandboxed automation turn, fall
    back to shell-first navigation instead of trying to bootstrap tmux
- Use shell-first only for tiny local edits, README wording, or when JetBrains
  is unavailable after a normal retry.

## Doc Routing and Planning Descent
- `docs/plans/` = planning synthesis, roadmap bridges, crosswalks, and sequencing.
- `docs/prd/` = product requirements and milestone intent.
- `docs/sdd/` = software or system design surfaces.
- `docs/hld/` = high-level design.
- `docs/lld/` = low-level design.
- `docs/task/` = active bounded execution surfaces.
- `docs/issues/` = durable blockers, defects, review findings, and `next_action` notes.
- `docs/gaps/` = unresolved missing capability or known design holes.
- `docs/project/` = stable repo reality, ownership, and status surfaces.
- `docs/done/` = completed slices and closeout records when present.
- `docs/handoff/` = continuation and operator handoff surfaces when present.
- `docs/test/` = validation procedures, fixtures, and benchmark notes.
- Keep `SQL` as truth, `LanceDB` as retrieval memory, `YAML` as policy, and `QMD` as evidence.
- Treat Hindsight as memory support, not runtime authority.

## Repo Surface Quick Routing
- `prd.json` and `progress.txt` = canonical story and carry-forward truth.
- `.ai/dropbox/` = live working exchange, receipts, lane outputs, and machine-visible status.
- `.codex/` = repo-local Codex profiles and hook plumbing for the named `trader` and `task` lanes.
- `docs/handoff/` = verbose human-readable continuation notes after a bounded slice is complete.
- `docs/` and repo code/config/tests = durable repo truth; handoff notes and dropbox receipts must point back here instead of replacing it.

## Artifact Hygiene
- Do not commit repo-understanding caches, local automation logs, raw receipts,
  or generated proposal/review packets unless a human explicitly promotes them
  into durable repo truth.
- Generated helpers such as `.codegraph/`, `.claude/`, `graphify-out/cache/`,
  `automation/state/`, and `training/automation/{logs,receipts,state}/` are
  local working artifacts.
- Generated docs under `docs/proposals/next_*.md` and
  `docs/reports/*_review.md` are draft packets until promoted into a stable
  `docs/task/`, `docs/issues/`, `docs/gaps/`, `docs/handoff/`, or canonical
  evidence surface.
- If a cleanup needs to preserve generated output, compress it under ignored
  `data/archive/` first; do not move tracked docs or `.ai/dropbox` history into
  an archive without a dedicated cleanup slice.

## Superpowers Routing
- Use `superpowers:writing-plans` before multi-step design or sequencing work.
- Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` when implementing a settled plan.
- Use `superpowers:systematic-debugging` before non-trivial bugfixes or failing verification loops.
- Use `superpowers:verification-before-completion` before claiming success, pushing, or handing off a bounded slice.

# AGENTS.md

## Mission
- Build and maintain a paper-first trading and research engine with explicit contracts, reproducible evidence, and auditable decision paths.
- Support both trading-engineering work and software-engineering work without allowing hidden authority drift.
- Keep runtime trading logic, research logic, memory, and policy governance clearly separated.

## Constitutional Rules
- Paper trading only unless scope is explicitly widened by the operator.
- No agent may place live trades, route live orders, or weaken risk controls by implication.
- Models suggest; the engine decides; the risk gate is final.
- Proposal truth and proposal-review truth are evidence surfaces only; they do not grant runtime authority by themselves.
- Proposal-comparison truth and supersession truth are evidence surfaces only; they do not grant runtime authority by themselves.
- Current repo truth comes from code, config, schemas, docs, and tests — not from memory tools or editor state.
- Hindsight and other memory systems are support surfaces only; they never override repo truth.
- JetBrains, MCP, indexes, and IDE context are navigation aids only; they are not authoritative by themselves.
- Prefer minimal, reversible, layer-respecting changes over broad refactors.
- Any change that affects runtime authority, strategy eligibility, risk behavior, or promotion state must be treated as governance-sensitive.

## Read Order
1. This `AGENTS.md`
2. Relevant playbooks in `AGENTS/`
3. Repo README / current architecture docs / source docs
4. Current code, configs, schemas, and tests in the touched area
5. Hindsight or other memory receipts only if needed for context or comparison

## Execution Loop
1. Classify the task.
   - engineering
   - trading research
   - policy/governance
   - runtime bug
   - docs/config sync
2. Read this file and only the playbooks needed for the task.
3. Reconstruct current repo truth from code/config/tests/docs before proposing changes.
4. Pull memory context only as supporting evidence.
5. Identify the owning layer and the contracts touched.
6. Make the smallest valid change.
7. Run the strongest relevant checks.
8. Record receipts: files changed, commands run, results, open risks, and follow-ups.
9. Update docs/config/tests when behavior changes.
10. Do not self-promote runtime behavior; route promotion-sensitive changes through governance.

## Layer Ownership Law
- `source/` owns provider access, raw capture, normalization, and source health.
- `features/` owns deterministic feature and label materialization.
- `condition/` owns regime and condition scoring.
- `trajectory/` owns advisory forecasting and scenario generation only.
- `policy/` owns strategy eligibility, parameter surfaces, and decision traceability.
- `risk/` owns hard vetoes, halts, and conservative controls.
- `settlement/` owns paper fills, paper session state, metrics, and report generation.
- `research_loop/` owns experiment comparison, shadow evaluation, and bounded improvement proposals.

Agents must not silently cross multiple layers in one change unless the task explicitly requires an integration owner.

## Memory Law
- Memory may help with:
  - prior decisions
  - prior bugs
  - prior experiments
  - prior operator preferences
- Memory may not:
  - redefine current contracts
  - override tests
  - replace current policy
  - justify undocumented runtime changes

## Validation Law
- Always run the strongest relevant validation for the touched area.
- Behavior changes require corresponding test or receipt updates.
- Report exact commands run and their results.
- If a check could not be run, say so explicitly and explain why.

## Required Receipts
Every non-trivial change should produce:
- files changed
- intent of change
- commands run
- results observed
- docs/config/tests updated or not
- open risks
- recommended next step

## Playbooks
- `AGENTS/engineering-flow.md`
- `AGENTS/trader-doctrine.md`
- `AGENTS/strategy-policy.md`
- `AGENTS/memory-hindsight.md`
- `AGENTS/jetbrains-mcp-workspace.md`

## Default Safe Action
When evidence is weak, state is stale, policy is ambiguous, or validation is incomplete, prefer:
- no trade
- no promotion
- no scope widening
- no hidden refactor
