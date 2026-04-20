"""Repo-owned training wrappers over the adaptive paper-practice runtime."""

from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import orjson
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime
from d5_trading_engine.research_loop.research_profiles import (
    get_research_profile,
    resolve_research_profile_schema_path,
    resolve_research_profiles_path,
    summarize_research_profile,
)
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = orjson.loads(path.read_bytes())
    except FileNotFoundError:
        return {}
    except orjson.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _merge_historical_cache_status(
    warehouse_status: dict[str, Any],
    latest_source_collection: dict[str, Any],
) -> dict[str, Any]:
    """Expose capture-vs-warehouse completeness without flattening them together."""
    merged = dict(warehouse_status)
    merged["completeness_basis"] = "warehouse(raw+parquet+sql)"
    merged["warehouse_completed_day_count"] = warehouse_status.get("completed_day_count", 0)
    merged["warehouse_missing_day_count"] = warehouse_status.get("missing_day_count", 0)
    merged["warehouse_next_missing_date"] = warehouse_status.get("next_missing_date", "")

    capture_after = latest_source_collection.get("historical_cache_after")
    if isinstance(capture_after, dict):
        merged["capture_complete"] = bool(capture_after.get("complete", False))
        merged["capture_completed_day_count"] = capture_after.get("completed_day_count", 0)
        merged["capture_missing_day_count"] = capture_after.get("missing_day_count", 0)
        merged["capture_next_missing_date"] = capture_after.get("next_missing_date", "")
        merged["capture_latest_completed_date"] = capture_after.get("latest_completed_date", "")

    return merged


def _merge_training_status(
    db_status: dict[str, Any],
    status_receipt: dict[str, Any],
) -> dict[str, Any]:
    """Prefer the latest paper-practice receipt for operator-facing loop state."""
    merged = deepcopy(db_status)
    receipt_loop_state = status_receipt.get("loop_state")
    conflicts: list[dict[str, Any]] = []
    terminal_loop_statuses = {"completed", "failed", "bootstrap_completed"}

    if isinstance(receipt_loop_state, dict) and receipt_loop_state:
        receipt_loop_run_id = str(receipt_loop_state.get("loop_run_id") or "")
        receipt_loop_status = str(receipt_loop_state.get("status") or "")
        receipt_decision_id = str(receipt_loop_state.get("latest_decision_id") or "")
        receipt_session_key = str(receipt_loop_state.get("latest_session_key") or "")

        if (
            merged.get("latest_loop_run_id")
            and receipt_loop_run_id
            and merged.get("latest_loop_run_id") != receipt_loop_run_id
        ):
            conflicts.append(
                {
                    "field": "latest_loop_run_id",
                    "db_value": merged.get("latest_loop_run_id", ""),
                    "receipt_value": receipt_loop_run_id,
                }
            )
        if (
            merged.get("latest_loop_status")
            and receipt_loop_status
            and merged.get("latest_loop_status") != receipt_loop_status
        ):
            conflicts.append(
                {
                    "field": "latest_loop_status",
                    "db_value": merged.get("latest_loop_status", ""),
                    "receipt_value": receipt_loop_status,
                }
            )

        merged["receipt_loop_state"] = receipt_loop_state
        effective_loop_run_id = receipt_loop_run_id or merged.get("latest_loop_run_id", "")
        effective_loop_status = receipt_loop_status or merged.get("latest_loop_status", "")
        # A stale receipt should not keep a finished loop looking active forever.
        if (
            receipt_loop_status == "running"
            and str(merged.get("latest_loop_status") or "") in terminal_loop_statuses
            and (
                not receipt_loop_run_id
                or receipt_loop_run_id == str(merged.get("latest_loop_run_id") or "")
            )
        ):
            effective_loop_run_id = str(merged.get("latest_loop_run_id") or effective_loop_run_id)
            effective_loop_status = str(merged.get("latest_loop_status") or effective_loop_status)
        merged["effective_loop_run_id"] = effective_loop_run_id
        merged["effective_loop_status"] = effective_loop_status
        merged["effective_latest_decision_id"] = receipt_decision_id or merged.get(
            "latest_decision_id", ""
        )
        merged["effective_latest_session_key"] = receipt_session_key or merged.get(
            "open_session_key", ""
        )
    else:
        merged["effective_loop_run_id"] = merged.get("latest_loop_run_id", "")
        merged["effective_loop_status"] = merged.get("latest_loop_status", "")
        merged["effective_latest_decision_id"] = merged.get("latest_decision_id", "")
        merged["effective_latest_session_key"] = merged.get("open_session_key", "")

    merged["status_conflicts"] = conflicts
    return merged


def _summarize_trader_lane_status(
    lane_sessions: dict[str, Any],
    watcher_status: dict[str, Any],
) -> dict[str, Any]:
    """Return the operator-facing summary of the persistent trader lane."""
    trader = lane_sessions.get("trader")
    if not isinstance(trader, dict):
        return {
            "present": False,
            "watcher_status": watcher_status.get("status", ""),
            "watcher_last_event_id": watcher_status.get("last_event_id", ""),
            "watcher_last_dispatch_ok": watcher_status.get("last_dispatch_ok"),
        }

    return {
        "present": True,
        "mode": trader.get("mode", ""),
        "profile": trader.get("profile", ""),
        "session_id": trader.get("session_id", ""),
        "thread_id": trader.get("thread_id", ""),
        "last_event_id": trader.get("last_event_id", ""),
        "updated_at_utc": trader.get("updated_at_utc", ""),
        "stale_after_hours": trader.get("stale_after_hours", ""),
        "watcher_status": watcher_status.get("status", ""),
        "watcher_last_event_id": watcher_status.get("last_event_id", ""),
        "watcher_last_dispatch_ok": watcher_status.get("last_dispatch_ok"),
    }


def _summarize_governor_status(
    review_receipt: dict[str, Any],
    priority_receipt: dict[str, Any],
) -> dict[str, Any]:
    latest_action = str(
        priority_receipt.get("governor_action")
        or review_receipt.get("governor_action")
        or ""
    )
    latest_updated_at = str(
        priority_receipt.get("updated_at")
        or review_receipt.get("updated_at")
        or ""
    )
    policy_id = str(
        priority_receipt.get("governor_policy_id")
        or review_receipt.get("governor_policy_id")
        or ""
    )
    return {
        "present": bool(policy_id or latest_action),
        "policy_id": policy_id,
        "latest_action": latest_action,
        "latest_review_action": str(review_receipt.get("governor_action") or ""),
        "latest_priority_action": str(priority_receipt.get("governor_action") or ""),
        "latest_reason_codes": priority_receipt.get("governor_reason_codes")
        or review_receipt.get("governor_reason_codes")
        or [],
        "latest_updated_at": latest_updated_at,
    }


def _selected_research_profile(settings: Settings) -> dict[str, Any]:
    repo_root = settings.repo_root
    profile = get_research_profile(settings.trader_research_profile, repo_root=repo_root)
    payload = summarize_research_profile(profile)
    payload["catalog_path"] = str(resolve_research_profiles_path(repo_root))
    payload["schema_path"] = str(resolve_research_profile_schema_path(repo_root))
    return payload


class TrainingRuntime:
    """Expose a stable training surface for CLI and automation wrappers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.practice = PaperPracticeRuntime(self.settings)

    @property
    def workspace_root(self) -> Path:
        return self.settings.repo_root / "training"

    @property
    def state_root(self) -> Path:
        return self.settings.repo_root / ".ai" / "dropbox" / "state"

    def bootstrap(self, *, training_profile_name: str | None = None) -> dict[str, Any]:
        result = self.practice.run_bootstrap(training_profile_name=training_profile_name)
        artifact_dir = Path(result["artifact_dir"])
        artifact_paths = [
            str(artifact_dir / "bootstrap_summary.json"),
            str(artifact_dir / "report.qmd"),
        ]
        return {
            "status": "completed",
            "run_id": result["bootstrap_id"],
            "artifact_dir": str(artifact_dir),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": result["active_revision_id"],
            "workspace_root": "training",
            "next_command": "d5 training walk-forward --json",
            "bootstrap": result,
        }

    def hydrate_history(
        self,
        *,
        max_days: int | None = None,
        training_profile_name: str | None = None,
    ) -> dict[str, Any]:
        cache_status = self.practice.historical_cache_status()
        if training_profile_name is None and cache_status["complete"]:
            return {
                "status": "noop",
                "run_id": "historical_cache_complete",
                "artifact_dir": str(self.settings.data_dir / "research" / "massive_minute_aggs"),
                "artifact_paths": [],
                "active_profile_revision_id": self.practice.ensure_active_profile()["active_revision_id"],
                "workspace_root": "training",
                "next_command": "d5 training collect --json",
                "historical_cache_status": cache_status,
            }

        result = self.practice.hydrate_history(
            max_days=max_days,
            training_profile_name=training_profile_name,
        )
        artifact_dir = Path(result["artifact_dir"])
        artifact_paths = [
            str(artifact_dir / "capture_summary.json"),
            str(artifact_dir / "report.qmd"),
        ]
        return {
            "status": result.get("status", "completed"),
            "run_id": result.get("batch_id") or result.get("run_id") or "historical_cache",
            "artifact_dir": str(artifact_dir),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": self.practice.ensure_active_profile()["active_revision_id"],
            "workspace_root": "training",
            "next_command": "d5 training status --json",
            "historical_cache_status": self.practice.historical_cache_status(),
            "hydrate_history": result,
        }

    def collect(
        self,
        *,
        max_massive_days: int = 1,
        include_helius: bool = False,
        include_jupiter: bool = True,
    ) -> dict[str, Any]:
        result = self.practice.run_source_collection(
            max_massive_days=max_massive_days,
            include_helius=include_helius,
            include_jupiter=include_jupiter,
        )
        artifact_dir = Path(result["artifact_dir"])
        artifact_paths = [
            str(artifact_dir / "summary.json"),
            str(artifact_dir / "report.qmd"),
        ]
        return {
            "status": result.get("status", "completed"),
            "run_id": result["collect_id"],
            "artifact_dir": str(artifact_dir),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": self.practice.ensure_active_profile()["active_revision_id"],
            "workspace_root": "training",
            "next_command": "d5 training status --json",
            "historical_cache_status": result["historical_cache_after"],
            "collect": result,
        }

    def walk_forward(self, *, training_profile_name: str | None = None) -> dict[str, Any]:
        result = self.practice.run_backtest_walk_forward(
            training_profile_name=training_profile_name,
        )
        artifact_dir = Path(result["artifact_dir"])
        artifact_paths = [
            str(artifact_dir / "summary.json"),
            str(artifact_dir / "report.qmd"),
        ]
        return {
            "status": result.get("status", "completed"),
            "run_id": result["run_id"],
            "artifact_dir": str(artifact_dir),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": result["active_revision_id"],
            "workspace_root": "training",
            "next_command": "d5 training review --json",
            "walk_forward": result,
        }

    def loop(
        self,
        *,
        with_helius_ws: bool = False,
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        result = self.practice.run_loop(
            with_helius_ws=with_helius_ws,
            max_iterations=max_iterations,
        )
        latest_trade_receipt = result.get("latest_trade_receipt", {}) or {}
        artifact_paths = []
        if self._state_path("paper_practice_status.json").exists():
            artifact_paths.append(str(self._state_path("paper_practice_status.json")))
        if self._state_path("paper_practice_latest_trade_receipt.json").exists():
            artifact_paths.append(str(self._state_path("paper_practice_latest_trade_receipt.json")))
        if self._state_path("paper_practice_latest_profile_revision.json").exists():
            artifact_paths.append(str(self._state_path("paper_practice_latest_profile_revision.json")))
        return {
            "status": result.get("status", "completed"),
            "run_id": result["loop_run_id"],
            "artifact_dir": str(self.state_root),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": result["active_revision_id"],
            "workspace_root": "training",
            "iterations_completed": result.get("iterations_completed", 0),
            "latest_trade_receipt": latest_trade_receipt,
            "next_command": "d5 training status --json",
            "loop": result,
        }

    def status(self) -> dict[str, Any]:
        payload = self.practice.get_status()
        cache_status = self.practice.historical_cache_status()
        selected_research_profile = _selected_research_profile(self.settings)
        artifact_paths = []
        for name in (
            "paper_practice_status.json",
            "paper_practice_latest_trade_receipt.json",
            "paper_practice_latest_profile_revision.json",
            "source_collection_status.json",
        ):
            path = self._state_path(name)
            if path.exists():
                artifact_paths.append(str(path))
        watcher_status_path = self.workspace_root / "automation" / "state" / "watcher_status.json"
        lane_sessions_path = self.workspace_root / "automation" / "state" / "lane_sessions.json"
        if watcher_status_path.exists():
            artifact_paths.append(str(watcher_status_path))
        if lane_sessions_path.exists():
            artifact_paths.append(str(lane_sessions_path))

        latest_receipt_status = _load_json(self._state_path("paper_practice_status.json"))
        latest_source_collection = _load_json(self._state_path("source_collection_status.json"))
        latest_review_receipt = _load_json(
            self._state_path("research_proposal_review_receipt.json")
        )
        latest_priority_receipt = _load_json(
            self._state_path("research_proposal_priority_receipt.json")
        )
        watcher_status = _load_json(watcher_status_path)
        lane_sessions = _load_json(lane_sessions_path)
        merged_cache_status = _merge_historical_cache_status(cache_status, latest_source_collection)
        merged_training_status = _merge_training_status(payload, latest_receipt_status)
        governor_status = _summarize_governor_status(
            latest_review_receipt,
            latest_priority_receipt,
        )
        selected_training_profile = payload.get("selected_training_profile", {})
        historical_ladder_completed = bool(
            (latest_receipt_status.get("loop_state") or {}).get("historical_ladder_completed")
        )
        effective_loop_status = str(merged_training_status.get("effective_loop_status") or "")
        if effective_loop_status == "running":
            next_command = "d5 training status --json"
        elif selected_training_profile.get("ready") and not historical_ladder_completed:
            next_command = "d5 training bootstrap --json"
        elif historical_ladder_completed:
            next_command = "d5 training loop --json"
        elif not cache_status["complete"]:
            next_command = "d5 training collect --json"
        else:
            next_command = "d5 training review --json"
        return {
            "status": "ok",
            "run_id": merged_training_status.get("effective_loop_run_id")
            or payload.get("latest_loop_run_id")
            or "training_status",
            "artifact_dir": str(self.workspace_root),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": payload["active_revision_id"],
            "workspace_root": "training",
            "next_command": next_command,
            "historical_cache_status": merged_cache_status,
            "selected_training_profile": selected_training_profile,
            "selected_training_regimen": selected_training_profile,
            "selected_research_profile": selected_research_profile,
            "selected_research_profile_name": selected_research_profile["name"],
            "selected_research_profile_summary": selected_research_profile["summary"],
            "training_profile_readiness": payload.get("training_profile_readiness", {}),
            "training_regimen_readiness": payload.get("training_profile_readiness", {}),
            "latest_source_collection": latest_source_collection,
            "automation_status": watcher_status,
            "trader_lane_status": _summarize_trader_lane_status(lane_sessions, watcher_status),
            "governor_status": governor_status,
            "training_status": merged_training_status,
        }

    def review(self) -> dict[str, Any]:
        review_id = f"training_review_{uuid.uuid4().hex[:12]}"
        artifact_dir = self.settings.data_dir / "research" / "training" / "reviews" / review_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        status_payload = self.status()
        latest_backtest_summary = self._latest_json(
            self.settings.data_dir / "research" / "paper_practice" / "backtests",
            "summary.json",
        )
        latest_bootstrap_summary = self._latest_json(
            self.settings.data_dir / "research" / "paper_practice" / "bootstrap",
            "bootstrap_summary.json",
        )
        latest_trade_receipt = _load_json(self._state_path("paper_practice_latest_trade_receipt.json"))
        latest_profile_revision = _load_json(self._state_path("paper_practice_latest_profile_revision.json"))
        selected_research_profile = status_payload.get("selected_research_profile", {})
        governor_status = status_payload.get("governor_status", {})

        summary = {
            "status": "completed",
            "run_id": review_id,
            "workspace_root": "training",
            "active_profile_revision_id": status_payload["active_profile_revision_id"],
            "selected_training_profile": status_payload.get("selected_training_profile", {}),
            "selected_training_regimen": status_payload.get("selected_training_profile", {}),
            "selected_research_profile": selected_research_profile,
            "selected_research_profile_name": selected_research_profile.get("name", ""),
            "selected_research_profile_summary": selected_research_profile.get("summary", ""),
            "governor_status": governor_status,
            "training_profile_readiness": status_payload.get("training_profile_readiness", {}),
            "training_regimen_readiness": status_payload.get("training_profile_readiness", {}),
            "latest_loop_run_id": status_payload["training_status"].get("latest_loop_run_id", ""),
            "open_session_key": status_payload["training_status"].get("open_session_key", ""),
            "latest_backtest_run_id": latest_backtest_summary.get("run_id", ""),
            "latest_backtest_window_count": latest_backtest_summary.get("window_count", 0),
            "historical_ladder_completed": latest_bootstrap_summary.get("completed_ladder")
            or bool((latest_bootstrap_summary.get("backtest_result") or {}).get("completed_ladder")),
            "latest_trade_receipt": latest_trade_receipt,
            "latest_profile_revision": latest_profile_revision,
            "latest_backtest_summary": latest_backtest_summary,
            "latest_bootstrap_summary": latest_bootstrap_summary,
            "artifact_dir": str(artifact_dir),
            "artifact_paths": [
                str(artifact_dir / "summary.json"),
                str(artifact_dir / "report.qmd"),
            ],
            "next_command": "d5 training loop --max-iterations 1 --json",
        }
        write_json_artifact(
            artifact_dir / "summary.json",
            summary,
            owner_type="training_review",
            owner_key=review_id,
            artifact_type="training_review_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "experiment_run.qmd",
                title="training review",
                metadata=trading_report_metadata(
                    report_kind="training_review",
                    run_id=review_id,
                    owner_type="training_review",
                    owner_key=review_id,
                    profile_revision_id=status_payload["active_profile_revision_id"],
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="15m",
                    summary_path="summary.json",
                    config_path="summary.json",
                    selected_research_profile=summary["selected_research_profile_name"] or None,
                ),
                summary_lines=[
                    f"- review id: `{review_id}`",
                    f"- active revision: `{summary['active_profile_revision_id']}`",
                    f"- selected training profile: `{summary['selected_training_profile'].get('name', 'none')}`",
                    f"- selected research profile: `{summary['selected_research_profile_name'] or 'none'}`",
                    f"- latest loop run: `{summary['latest_loop_run_id'] or 'none'}`",
                    f"- latest backtest run: `{summary['latest_backtest_run_id'] or 'none'}`",
                    f"- historical ladder completed: `{summary['historical_ladder_completed']}`",
                ],
                sections=[
                    (
                        "Market / Source Context",
                        [
                            f"- historical cache complete: `{status_payload['historical_cache_status']['complete']}`",
                            f"- next missing date: `{status_payload['historical_cache_status']['next_missing_date'] or 'none'}`",
                            f"- selected training profile ready: `{summary['selected_training_profile'].get('ready', False)}`",
                            f"- selected research profile summary: {summary['selected_research_profile_summary'] or 'none'}",
                            f"- latest source collection run: `{status_payload['latest_source_collection'].get('collect_id', 'none')}`",
                            "- evidence plane: SQL as truth, QMD as review packet, thin JSON only for watcher state",
                        ],
                    ),
                    (
                        "Strategy / Profile",
                        [
                            f"- active profile revision: `{summary['active_profile_revision_id']}`",
                            f"- latest profile source: `{latest_profile_revision.get('revision_id', 'none')}`",
                            f"- research profile objective: {selected_research_profile.get('primary_objective', 'none')}",
                            f"- research profile preferred sources: `{', '.join(selected_research_profile.get('preferred_sources', [])) or 'none'}`",
                            f"- research profile preferred metrics: `{', '.join(selected_research_profile.get('preferred_metrics', [])) or 'none'}`",
                            f"- workspace root: `training/`",
                        ],
                    ),
                    (
                        "Profile Governor",
                        [
                            f"- policy id: `{governor_status.get('policy_id', 'none') or 'none'}`",
                            f"- latest action: `{governor_status.get('latest_action', 'none') or 'none'}`",
                            f"- latest review action: `{governor_status.get('latest_review_action', 'none') or 'none'}`",
                            f"- latest priority action: `{governor_status.get('latest_priority_action', 'none') or 'none'}`",
                        ],
                    ),
                    (
                        "Trade / Replay Outcome",
                        [
                            f"- windows completed: `{summary['latest_backtest_window_count']}`",
                            f"- latest trade session key: `{latest_trade_receipt.get('session_key', 'none')}`",
                            f"- latest trade close reason: `{latest_trade_receipt.get('close_reason', 'n/a')}`",
                        ]
                        if summary["latest_backtest_run_id"]
                        else ["- no historical walk-forward summary found", "- no latest trade receipt found"],
                    ),
                    (
                        "Failure Attribution",
                        [
                            (
                                "- weakest surface: `data coverage`"
                                if not status_payload["historical_cache_status"]["complete"]
                                else "- weakest surface: `inconclusive / sample too small`"
                            ),
                        ]
                    ),
                    (
                        "Bounded Next Change",
                        [
                            "- default action: `keep` current profile unless a bounded review proposal beats the latest accepted baseline",
                            f"- next command: `{summary['next_command']}`",
                        ],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="training_review",
            owner_key=review_id,
            artifact_type="training_review_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        return summary

    def _state_path(self, filename: str) -> Path:
        return self.state_root / filename

    def _latest_json(self, root: Path, filename: str) -> dict[str, Any]:
        paths = sorted(root.glob(f"*/{filename}"), key=lambda path: path.stat().st_mtime, reverse=True)
        for path in paths:
            payload = _load_json(path)
            if payload:
                return payload
        return {}
