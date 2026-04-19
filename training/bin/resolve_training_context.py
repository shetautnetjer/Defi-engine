#!/usr/bin/env python3
"""Resolve repo-owned training context for watcher-driven Codex tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from d5_trading_engine.config.settings import Settings
from d5_trading_engine.research_loop.profile_governor import (
    resolve_profile_governor_decision_schema_path,
    resolve_profile_governor_policy_path,
    resolve_profile_governor_prompt_path,
    resolve_profile_governor_scorecard_schema_path,
)
from d5_trading_engine.research_loop.research_profiles import (
    get_research_profile,
    resolve_research_profile_schema_path,
    resolve_research_profiles_path,
    summarize_research_profile,
)


ALLOWED_CHANGE_SURFACES = [
    "preferred strategy family",
    "strategy report path",
    "minimum condition confidence",
    "stop loss bps",
    "take profit bps",
    "time stop bars",
    "cooldown bars",
    "source-set selection flags",
    "timeframe selection flags",
]


TARGET_SURFACE_BY_EVENT = {
    "paper_session_closed": "paper-profile thresholds or preferred strategy family",
    "experiment_completed": "one bounded experiment surface compared against the latest accepted baseline",
    "condition_run_completed": "condition model or regime semantic mapping",
    "feature_run_completed": "feature set or source/timeframe selection",
    "tests_failed": "smallest engineering repair needed to restore the training lane",
}


KEEP_REVERT_SHADOW_RULE_BY_EVENT = {
    "paper_session_closed": (
        "Keep the active paper profile unless one bounded paper-profile change is "
        "clearly supported by the closed-session evidence; revert regressions and "
        "shadow mixed ideas."
    ),
    "experiment_completed": (
        "Keep the current accepted baseline unless the candidate beats it on the "
        "rubric and evidence stack; revert regressions and shadow inconclusive ideas."
    ),
    "condition_run_completed": (
        "Keep the current condition baseline unless the new run improves condition "
        "quality with plausible downstream trading benefit; otherwise shadow."
    ),
    "feature_run_completed": (
        "Keep the current feature baseline unless the new feature surface improves "
        "downstream evidence; otherwise revert or shadow."
    ),
    "tests_failed": (
        "Keep trading behavior fixed; only repair the smallest blocking engineering "
        "failure needed to restore training or paper-review flow."
    ),
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_json(root: Path, filename: str) -> tuple[Path | None, dict[str, Any]]:
    if not root.exists():
        return None, {}
    paths = sorted(
        root.glob(f"*/{filename}"),
        key=lambda candidate: candidate.stat().st_mtime,
        reverse=True,
    )
    for path in paths:
        payload = _load_json(path)
        if payload:
            return path, payload
    return None, {}


def _first_existing(paths: list[Path | None]) -> Path | None:
    for path in paths:
        if path is not None and path.exists():
            return path
    return None


def _resolve_repo_root(raw_repo_root: str | None, explicit_repo_root: Path | None) -> Path:
    if explicit_repo_root is not None:
        return explicit_repo_root.resolve()
    if raw_repo_root:
        return Path(raw_repo_root).resolve()
    return Path(__file__).resolve().parents[2]


def _relative_to_repo(path: Path | None, repo_root: Path) -> str:
    if path is None:
        return ""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _selected_research_profile(repo_root: Path) -> dict[str, Any]:
    env_file = repo_root / ".env"
    settings = Settings(
        _env_file=env_file if env_file.exists() else None,
        repo_root=repo_root,
    )
    profile = get_research_profile(
        settings.trader_research_profile,
        repo_root=repo_root,
    )
    payload = summarize_research_profile(profile)
    payload["catalog_path"] = _relative_to_repo(resolve_research_profiles_path(repo_root), repo_root)
    payload["schema_path"] = _relative_to_repo(
        resolve_research_profile_schema_path(repo_root),
        repo_root,
    )
    return payload


def _event_payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def resolve_training_context(event: dict[str, Any], *, repo_root: Path | None = None) -> dict[str, Any]:
    payload = _event_payload(event)
    resolved_repo_root = _resolve_repo_root(event.get("repo_root"), repo_root)

    training_root = resolved_repo_root / "training"
    state_root = resolved_repo_root / ".ai" / "dropbox" / "state"
    data_root = resolved_repo_root / "data" / "research"

    root_agents = resolved_repo_root / "AGENTS.md"
    training_agents = training_root / "AGENTS.md"
    training_readme = training_root / "README.md"
    trading_harness = training_root / "trading_agent_harness.md"
    training_program = training_root / "program.md"
    training_rubric = training_root / "rubrics" / "training_regime_rubric.md"
    qmd_contract = resolved_repo_root / "docs" / "task" / "trading_qmd_report_contract.md"
    research_profiles = resolve_research_profiles_path(resolved_repo_root)
    research_profile_schema = resolve_research_profile_schema_path(resolved_repo_root)
    governor_policy = resolve_profile_governor_policy_path(resolved_repo_root)
    governor_scorecard_schema = resolve_profile_governor_scorecard_schema_path(
        resolved_repo_root
    )
    governor_decision_schema = resolve_profile_governor_decision_schema_path(
        resolved_repo_root
    )
    governor_prompt = resolve_profile_governor_prompt_path(resolved_repo_root)

    training_status = _load_json(state_root / "paper_practice_status.json")
    latest_trade_receipt = _load_json(state_root / "paper_practice_latest_trade_receipt.json")
    latest_profile_revision = _load_json(state_root / "paper_practice_latest_profile_revision.json")
    latest_source_collection = _load_json(state_root / "source_collection_status.json")
    selected_research_profile = _selected_research_profile(resolved_repo_root)

    backtest_summary_path, backtest_summary = _latest_json(
        data_root / "paper_practice" / "backtests",
        "summary.json",
    )
    bootstrap_summary_path, bootstrap_summary = _latest_json(
        data_root / "paper_practice" / "bootstrap",
        "bootstrap_summary.json",
    )
    review_summary_path, review_summary = _latest_json(
        data_root / "training" / "reviews",
        "summary.json",
    )
    review_report_path = (
        review_summary_path.parent / "report.qmd" if review_summary_path is not None else None
    )

    resolved_qmd_reports = [
        str(path)
        for path in [
            *[resolved_repo_root / report for report in event.get("qmd_reports", []) if isinstance(report, str)],
            review_report_path,
            backtest_summary_path.parent / "report.qmd" if backtest_summary_path is not None else None,
            bootstrap_summary_path.parent / "report.qmd" if bootstrap_summary_path is not None else None,
        ]
        if path is not None and path.exists()
    ]

    primary_qmd_path = _first_existing(
        [
            resolved_repo_root / report
            for report in event.get("qmd_reports", [])
            if isinstance(report, str)
        ]
        + [
            review_report_path,
            backtest_summary_path.parent / "report.qmd" if backtest_summary_path is not None else None,
            bootstrap_summary_path.parent / "report.qmd" if bootstrap_summary_path is not None else None,
        ]
    )

    active_profile_revision_id = (
        latest_profile_revision.get("active_revision_id")
        or latest_profile_revision.get("revision_id")
        or training_status.get("active_revision_id")
        or payload.get("active_profile_revision_id")
        or ""
    )

    baseline_refs: list[str] = []
    if review_summary.get("latest_backtest_run_id"):
        baseline_refs.append(
            f"latest_backtest_run_id={review_summary['latest_backtest_run_id']}"
        )
    if training_status.get("latest_loop_run_id"):
        baseline_refs.append(
            f"latest_loop_run_id={training_status['latest_loop_run_id']}"
        )
    if backtest_summary.get("run_id"):
        baseline_refs.append(f"backtest_summary_run_id={backtest_summary['run_id']}")
    if bootstrap_summary.get("bootstrap_id"):
        baseline_refs.append(f"bootstrap_id={bootstrap_summary['bootstrap_id']}")
    if isinstance(payload.get("baseline_refs"), list):
        baseline_refs.extend(str(item) for item in payload["baseline_refs"])
    if not baseline_refs:
        baseline_refs.append("no explicit comparable baseline found")

    historical_cache_summary = (
        payload.get("historical_cache_status")
        or latest_source_collection.get("historical_cache_after")
        or training_status.get("historical_cache_status")
        or {}
    )
    if isinstance(historical_cache_summary, dict) and historical_cache_summary:
        historical_cache_line = (
            f"complete={historical_cache_summary.get('complete', False)}, "
            f"completed_day_count={historical_cache_summary.get('completed_day_count', 'n/a')}, "
            f"missing_day_count={historical_cache_summary.get('missing_day_count', 'n/a')}, "
            f"next_missing_date={historical_cache_summary.get('next_missing_date', 'n/a')}"
        )
    else:
        historical_cache_line = "historical cache status unavailable"

    active_profile_summary_parts = []
    if active_profile_revision_id:
        active_profile_summary_parts.append(f"revision={active_profile_revision_id}")
    if training_status.get("open_session_key"):
        active_profile_summary_parts.append(
            f"open_session_key={training_status['open_session_key']}"
        )
    if latest_trade_receipt.get("session_key"):
        active_profile_summary_parts.append(
            f"latest_session={latest_trade_receipt['session_key']}"
        )
    if latest_trade_receipt.get("close_reason"):
        active_profile_summary_parts.append(
            f"latest_close_reason={latest_trade_receipt['close_reason']}"
        )
    active_profile_summary = ", ".join(active_profile_summary_parts) or "no active profile summary available"

    event_type = str(event.get("event_type", ""))
    target_surface = str(
        payload.get("target_surface")
        or event.get("target_surface")
        or TARGET_SURFACE_BY_EVENT.get(event_type, "one bounded training surface")
    )
    keep_revert_shadow_rule = KEEP_REVERT_SHADOW_RULE_BY_EVENT.get(
        event_type,
        "Keep the current accepted baseline unless one bounded candidate clearly improves evidence; otherwise revert or shadow.",
    )

    training_doc_read_order = [
        _relative_to_repo(root_agents, resolved_repo_root),
        _relative_to_repo(training_agents, resolved_repo_root),
        _relative_to_repo(training_readme, resolved_repo_root),
        _relative_to_repo(trading_harness, resolved_repo_root),
        _relative_to_repo(training_program, resolved_repo_root),
        _relative_to_repo(training_rubric, resolved_repo_root),
        _relative_to_repo(qmd_contract, resolved_repo_root),
        _relative_to_repo(research_profiles, resolved_repo_root),
        _relative_to_repo(research_profile_schema, resolved_repo_root),
        _relative_to_repo(governor_policy, resolved_repo_root),
        _relative_to_repo(governor_scorecard_schema, resolved_repo_root),
        _relative_to_repo(governor_decision_schema, resolved_repo_root),
        _relative_to_repo(governor_prompt, resolved_repo_root),
    ]

    resolved_sql_refs = [str(item) for item in event.get("sql_refs", [])]
    if isinstance(payload.get("sql_refs"), list):
        resolved_sql_refs.extend(str(item) for item in payload["sql_refs"])

    return {
        "repo_root": str(resolved_repo_root),
        "doc_paths": {
            "root_agents": _relative_to_repo(root_agents, resolved_repo_root),
            "training_agents": _relative_to_repo(training_agents, resolved_repo_root),
            "training_readme": _relative_to_repo(training_readme, resolved_repo_root),
            "trading_harness": _relative_to_repo(trading_harness, resolved_repo_root),
            "training_program": _relative_to_repo(training_program, resolved_repo_root),
            "training_rubric": _relative_to_repo(training_rubric, resolved_repo_root),
            "qmd_contract": _relative_to_repo(qmd_contract, resolved_repo_root),
            "research_profiles": _relative_to_repo(research_profiles, resolved_repo_root),
            "research_profile_schema": _relative_to_repo(
                research_profile_schema,
                resolved_repo_root,
            ),
            "governor_policy": _relative_to_repo(governor_policy, resolved_repo_root),
            "governor_scorecard_schema": _relative_to_repo(
                governor_scorecard_schema,
                resolved_repo_root,
            ),
            "governor_decision_schema": _relative_to_repo(
                governor_decision_schema,
                resolved_repo_root,
            ),
            "governor_prompt": _relative_to_repo(governor_prompt, resolved_repo_root),
        },
        "training_doc_read_order": training_doc_read_order,
        "allowed_change_surfaces": ALLOWED_CHANGE_SURFACES,
        "target_surface": target_surface,
        "keep_revert_shadow_rule": keep_revert_shadow_rule,
        "active_profile_revision_id": active_profile_revision_id,
        "active_profile_summary": active_profile_summary,
        "historical_cache_summary": historical_cache_line,
        "baseline_refs": baseline_refs,
        "resolved_qmd_reports": [_relative_to_repo(Path(path), resolved_repo_root) for path in resolved_qmd_reports],
        "primary_qmd_path": _relative_to_repo(primary_qmd_path, resolved_repo_root),
        "resolved_sql_refs": resolved_sql_refs,
        "selected_research_profile": selected_research_profile,
        "selected_research_profile_name": selected_research_profile.get("name", ""),
        "selected_research_profile_summary": selected_research_profile.get(
            "summary",
            "no selected research profile available",
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve training context for watcher prompts.")
    parser.add_argument("--event-file", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=None)
    args = parser.parse_args()

    event = _load_json(args.event_file)
    resolved = resolve_training_context(event, repo_root=args.repo_root)
    print(json.dumps(resolved, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
