# 2026-04-18 AGENTS Topology And Handoff Doctrine

## Status

This slice tightened repo navigation and clarified which continuation surface
belongs where.

Current authoritative references:

- [AGENTS.md](../../AGENTS.md)
- [docs/README.md](../README.md)
- [.ai/README.md](../../.ai/README.md)
- [.ai/dropbox/README.md](../../.ai/dropbox/README.md)

## What Changed

- added folder-level navigation guidance at:
  - `src/d5_trading_engine/AGENTS.md`
  - `src/d5_trading_engine/storage/AGENTS.md`
  - `src/d5_trading_engine/research_loop/AGENTS.md`
  - `src/d5_trading_engine/models/AGENTS.md`
- added `docs/handoff/README.md` to define `docs/handoff/` as the durable
  human-readable continuation surface
- clarified the split between:
  - `.ai/dropbox/` for live working exchange and receipts
  - `docs/handoff/` for verbose human resume notes
  - `prd.json` and `progress.txt` for canonical story state
- added docs-contract coverage for the new navigation files and routing doctrine

## Validation

```bash
pytest -q tests/test_docs_contract.py
pytest -q tests/test_orchestration_contract.py
```

Observed results:

- `tests/test_docs_contract.py` -> `12 passed`
- `tests/test_orchestration_contract.py` -> `12 passed`

## Open Risks

- the worktree remains broadly dirty outside this focused navigation/docs slice
- `.ai/dropbox/**` is still an active control-plane surface with gitignore and
  staging expectations that do not line up perfectly in every script
- no commit or push should be treated as safe until the broader mixed worktree
  is reconciled intentionally

## Recommended Resume Point

If the next slice continues repo navigation and governance cleanup:

1. decide whether `scripts/agents/AGENTS.md` should be added as the next
   high-value navigation surface
2. reconcile the known `.ai/dropbox` gitignore versus staging mismatch in the
   control-plane scripts
3. only then define a clean commit boundary for the focused docs/governance
   changes
