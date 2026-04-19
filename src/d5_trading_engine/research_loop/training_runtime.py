"""Repo-owned training wrappers over the adaptive paper-practice runtime."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import orjson
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime
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

    def bootstrap(self) -> dict[str, Any]:
        result = self.practice.run_bootstrap()
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

    def hydrate_history(self, *, max_days: int | None = None) -> dict[str, Any]:
        cache_status = self.practice.historical_cache_status()
        if cache_status["complete"]:
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

        result = self.practice.hydrate_history(max_days=max_days)
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

    def walk_forward(self) -> dict[str, Any]:
        result = self.practice.run_backtest_walk_forward()
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
        latest_source_collection = _load_json(self._state_path("source_collection_status.json"))
        return {
            "status": "ok",
            "run_id": payload.get("latest_loop_run_id") or "training_status",
            "artifact_dir": str(self.workspace_root),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": payload["active_revision_id"],
            "workspace_root": "training",
            "next_command": (
                "d5 training collect --json"
                if not cache_status["complete"]
                else "d5 training review --json"
            ),
            "historical_cache_status": cache_status,
            "latest_source_collection": latest_source_collection,
            "training_status": payload,
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

        summary = {
            "status": "completed",
            "run_id": review_id,
            "workspace_root": "training",
            "active_profile_revision_id": status_payload["active_profile_revision_id"],
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
                ),
                summary_lines=[
                    f"- review id: `{review_id}`",
                    f"- active revision: `{summary['active_profile_revision_id']}`",
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
                            f"- latest source collection run: `{status_payload['latest_source_collection'].get('collect_id', 'none')}`",
                            "- evidence plane: SQL as truth, QMD as review packet, thin JSON only for watcher state",
                        ],
                    ),
                    (
                        "Strategy / Profile",
                        [
                            f"- active profile revision: `{summary['active_profile_revision_id']}`",
                            f"- latest profile source: `{latest_profile_revision.get('revision_id', 'none')}`",
                            f"- workspace root: `training/`",
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
