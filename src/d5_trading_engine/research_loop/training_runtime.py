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
from d5_trading_engine.reporting.qmd import render_qmd


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
        artifact_paths = []
        for name in (
            "paper_practice_status.json",
            "paper_practice_latest_trade_receipt.json",
            "paper_practice_latest_profile_revision.json",
        ):
            path = self._state_path(name)
            if path.exists():
                artifact_paths.append(str(path))
        return {
            "status": "ok",
            "run_id": payload.get("latest_loop_run_id") or "training_status",
            "artifact_dir": str(self.workspace_root),
            "artifact_paths": artifact_paths,
            "active_profile_revision_id": payload["active_revision_id"],
            "workspace_root": "training",
            "next_command": "d5 training review --json",
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
                summary_lines=[
                    f"- review id: `{review_id}`",
                    f"- active revision: `{summary['active_profile_revision_id']}`",
                    f"- latest loop run: `{summary['latest_loop_run_id'] or 'none'}`",
                    f"- latest backtest run: `{summary['latest_backtest_run_id'] or 'none'}`",
                    f"- historical ladder completed: `{summary['historical_ladder_completed']}`",
                ],
                sections=[
                    (
                        "Status",
                        [
                            f"- open session: `{summary['open_session_key'] or 'none'}`",
                            f"- workspace root: `training/`",
                            f"- next command: `{summary['next_command']}`",
                        ],
                    ),
                    (
                        "Backtest",
                        [
                            f"- windows completed: `{summary['latest_backtest_window_count']}`",
                        ]
                        if summary["latest_backtest_run_id"]
                        else ["- no historical walk-forward summary found"],
                    ),
                    (
                        "Latest Trade Receipt",
                        [
                            f"- session key: `{latest_trade_receipt.get('session_key', 'none')}`",
                            f"- close reason: `{latest_trade_receipt.get('close_reason', 'n/a')}`",
                        ]
                        if latest_trade_receipt
                        else ["- no latest trade receipt found"],
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
