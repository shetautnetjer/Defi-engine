# Repo Surface Map for Agent Navigation

## Human Entry

- `README.md`
- Notion page

## Repo Law

- `AGENTS.md`
- `training/AGENTS.md`
- `docs/project/current_runtime_truth.md`

## Runtime Core

- `src/d5_trading_engine/source/`
- `src/d5_trading_engine/features/`
- `src/d5_trading_engine/condition/`
- `src/d5_trading_engine/policy/`
- `src/d5_trading_engine/risk/`
- `src/d5_trading_engine/execution_intent/`
- `src/d5_trading_engine/settlement/`

## Research/Training

- `src/d5_trading_engine/research/`
- `src/d5_trading_engine/research_loop/`
- `training/`
- `data/research/`

## Agent Control Plane

- `.ai/`
- `.codex/`
- `training/automation/`

## Evidence

- SQL canonical DB
- QMD reports
- JSON receipts
- Parquet warehouse
- LanceDB derived summaries

## Rule

If an artifact is not in SQL/QMD/JSON receipt form, the agent must treat it as context, not proof.
