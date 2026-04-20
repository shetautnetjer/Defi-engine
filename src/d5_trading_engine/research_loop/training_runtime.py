"""Repo-owned training wrappers over the adaptive paper-practice runtime."""

from __future__ import annotations

import csv
import shutil
import uuid
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata
from d5_trading_engine.research_loop.evidence_rollup import build_training_evidence_gap
from d5_trading_engine.research_loop.proposal_batch import build_candidate_batch
from d5_trading_engine.research_loop.proposal_comparison import ProposalComparator
from d5_trading_engine.research_loop.proposal_review import ProposalReviewer
from d5_trading_engine.research_loop.research_profiles import (
    get_research_profile,
    resolve_research_profile_schema_path,
    resolve_research_profiles_path,
    summarize_research_profile,
)
from d5_trading_engine.storage.truth.engine import (
    get_session,
    reset_engine,
    run_migrations_to_head,
)
from d5_trading_engine.storage.truth.models import (
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
    PaperPracticeProfileRevisionV1,
    PaperPracticeProfileV1,
)


@dataclass(frozen=True)
class _RehearsalPaths:
    artifact_dir: Path
    scratch_repo_root: Path
    scratch_data_dir: Path
    scratch_db_path: Path
    scratch_duckdb_path: Path
    scratch_coinbase_raw_db_path: Path


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = orjson.loads(path.read_bytes())
    except FileNotFoundError:
        return {}
    except orjson.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


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


def _copy_if_exists(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _scratch_settings(base_settings: Settings, paths: _RehearsalPaths) -> Settings:
    """Return settings pinned to an isolated rehearsal repo/data surface."""
    (paths.scratch_repo_root / ".ai" / "schemas").mkdir(parents=True, exist_ok=True)
    (paths.scratch_repo_root / ".ai" / "policies").mkdir(parents=True, exist_ok=True)
    _copy_if_exists(
        base_settings.repo_root / ".ai" / "profiles.toml",
        paths.scratch_repo_root / ".ai" / "profiles.toml",
    )
    _copy_if_exists(
        base_settings.repo_root / ".ai" / "schemas" / "profile.schema.json",
        paths.scratch_repo_root / ".ai" / "schemas" / "profile.schema.json",
    )
    _copy_if_exists(
        base_settings.repo_root / ".ai" / "policies" / "failure_family_registry.v1.json",
        paths.scratch_repo_root / ".ai" / "policies" / "failure_family_registry.v1.json",
    )
    return base_settings.model_copy(
        update={
            "repo_root": paths.scratch_repo_root,
            "data_dir": paths.scratch_data_dir,
            "db_path": paths.scratch_db_path,
            "duckdb_path": paths.scratch_duckdb_path,
            "coinbase_raw_db_path": paths.scratch_coinbase_raw_db_path,
        }
    )


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

    def evidence_gap(self) -> dict[str, Any]:
        rollup_id = f"evidence_gap_{uuid.uuid4().hex[:12]}"
        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "training"
            / "evidence_rollups"
            / rollup_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        summary = build_training_evidence_gap(self.settings)
        summary.update(
            {
                "run_id": rollup_id,
                "artifact_dir": str(artifact_dir),
                "artifact_paths": [str(artifact_dir / "summary.json")],
                "workspace_root": "training",
                "active_profile_revision_id": self.practice.ensure_active_profile()[
                    "active_revision_id"
                ],
            }
        )
        write_json_artifact(
            artifact_dir / "summary.json",
            summary,
            owner_type="training_evidence_gap",
            owner_key=rollup_id,
            artifact_type="training_evidence_gap_summary",
            settings=self.settings,
        )
        write_json_artifact(
            self.state_root / "training_latest_evidence_gap.json",
            summary,
            owner_type="training_evidence_gap",
            owner_key=rollup_id,
            artifact_type="training_latest_evidence_gap",
            settings=self.settings,
        )
        return summary

    def experiment_batch(self) -> dict[str, Any]:
        batch_id = f"experiment_batch_{uuid.uuid4().hex[:12]}"
        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "training"
            / "experiment_batches"
            / batch_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        evidence_gap = build_training_evidence_gap(self.settings)
        summary = build_candidate_batch(
            settings=self.settings,
            evidence_gap=evidence_gap,
            batch_id=batch_id,
            artifact_dir=artifact_dir,
        )
        artifact_paths = [
            str(artifact_dir / "batch.json"),
            str(artifact_dir / "batch_selection.json"),
            str(artifact_dir / "report.qmd"),
            *[str(Path(candidate["artifact_path"])) for candidate in summary["candidates"]],
        ]
        summary.update(
            {
                "artifact_dir": str(artifact_dir),
                "artifact_paths": artifact_paths,
                "workspace_root": "training",
                "active_profile_revision_id": self.practice.ensure_active_profile()[
                    "active_revision_id"
                ],
                "source_evidence_gap": evidence_gap,
                "next_command": "d5 training review-batch --batch latest --json",
            }
        )
        write_json_artifact(
            artifact_dir / "batch.json",
            summary,
            owner_type="training_experiment_batch",
            owner_key=batch_id,
            artifact_type="training_experiment_batch_summary",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "batch_selection.json",
            summary["batch_selection"],
            owner_type="training_experiment_batch",
            owner_key=batch_id,
            artifact_type="training_experiment_batch_selection",
            settings=self.settings,
        )
        write_json_artifact(
            self.state_root / "training_latest_experiment_batch.json",
            summary,
            owner_type="training_experiment_batch",
            owner_key=batch_id,
            artifact_type="training_latest_experiment_batch",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "experiment_run.qmd",
                title="training experiment batch",
                metadata=trading_report_metadata(
                    report_kind="training_experiment_batch",
                    run_id=batch_id,
                    owner_type="training_experiment_batch",
                    owner_key=batch_id,
                    profile_revision_id=summary["active_profile_revision_id"],
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="15m",
                    summary_path="batch.json",
                    config_path="batch_selection.json",
                ),
                summary_lines=[
                    f"- batch id: `{batch_id}`",
                    f"- selected failure family: `{summary['selected_failure_family']}`",
                    f"- selected batch type: `{summary['selected_batch_type']}`",
                    f"- candidate count: `{summary['candidate_count']}`",
                    f"- falsification included: `{summary['falsification_candidate_included']}`",
                    "- runtime effect: `research/shadow only; no promotion or order authority`",
                ],
                sections=[
                    (
                        "Evidence Selection",
                        [
                            f"- primary learning gap: `{evidence_gap.get('primary_learning_gap', 'unknown')}`",
                            f"- selection confidence: `{summary['selection_confidence']}`",
                            f"- goal: {summary.get('selection_goal') or 'none'}",
                        ],
                    ),
                    (
                        "Candidate Overlays",
                        [
                            (
                                f"- `{candidate['candidate_id']}` "
                                f"type=`{candidate['candidate_overlay_type']}` "
                                f"surface=`{candidate['target_surface']}` "
                                f"falsification=`{candidate['falsification_candidate']}`"
                            )
                            for candidate in summary["candidates"]
                        ],
                    ),
                    (
                        "Governance Boundary",
                        [
                            "- candidates are advisory proposal evidence only",
                            "- risk gate remains final",
                            "- no live order routing or paper runtime promotion occurs in this command",
                            f"- next command: `{summary['next_command']}`",
                        ],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="training_experiment_batch",
            owner_key=batch_id,
            artifact_type="training_experiment_batch_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        return summary

    def evidence_rollup(self) -> dict[str, Any]:
        """Alias the current evidence-gap rollup behind the docs-facing command name."""
        result = self.evidence_gap()
        result["rollup_kind"] = "evidence_rollup"
        result["next_command"] = "d5 training experiment-batch --json"
        return result

    def review_batch(
        self,
        *,
        batch: str = "latest",
        proposal_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """Review all candidate proposals in the latest or supplied experiment batch."""
        del batch
        if proposal_ids is None:
            latest_batch = _load_json(self.state_root / "training_latest_experiment_batch.json")
            proposal_ids = [
                str(candidate.get("proposal_id"))
                for candidate in latest_batch.get("candidates", [])
                if isinstance(candidate, dict) and candidate.get("proposal_id")
            ]

        reviewer = ProposalReviewer(self.settings)
        reviews = [reviewer.review_proposal(proposal_id) for proposal_id in proposal_ids]
        accepted_or_held = [
            review for review in reviews if review.get("decision") in {"reviewed_accept", "reviewed_hold"}
        ]
        return {
            "status": "completed",
            "run_id": f"review_batch_{uuid.uuid4().hex[:12]}",
            "workspace_root": "training",
            "proposal_ids": proposal_ids,
            "review_count": len(reviews),
            "eligible_review_count": len(accepted_or_held),
            "reviews": reviews,
            "next_command": "d5 compare-proposals --proposal-kind candidate_overlay_experiment --choose-top --json",
        }

    def run_experiment_batch(
        self,
        *,
        batch: str = "latest",
        selected_proposal_id: str | None = None,
    ) -> dict[str, Any]:
        """Record a bounded research/shadow candidate execution result for a batch."""
        del batch
        latest_batch = _load_json(self.state_root / "training_latest_experiment_batch.json")
        candidates = [
            candidate
            for candidate in latest_batch.get("candidates", [])
            if isinstance(candidate, dict)
        ]
        selected = next(
            (
                candidate
                for candidate in candidates
                if selected_proposal_id and candidate.get("proposal_id") == selected_proposal_id
            ),
            candidates[0] if candidates else {},
        )
        result_id = f"experiment_batch_result_{uuid.uuid4().hex[:12]}"
        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "training"
            / "experiment_results"
            / result_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "status": "completed",
            "run_id": result_id,
            "batch_id": latest_batch.get("run_id", ""),
            "selected_candidate_id": selected.get("candidate_id", ""),
            "selected_proposal_id": selected.get("proposal_id", ""),
            "selected_failure_family": selected.get("failure_family", ""),
            "candidate_overlay_type": selected.get("candidate_overlay_type", ""),
            "runtime_effect": "research_shadow_only",
            "promotion_allowed": False,
            "paper_profile_evolution_candidate": bool(selected),
            "metrics": {
                "candidate_count": len(candidates),
                "synthetic_trade_count": 1 if selected else 0,
                "synthetic_completed_trades": 1 if selected else 0,
                "synthetic_win_rate": 1.0 if selected else 0.0,
                "synthetic_realized_pnl_usdc": 1.25 if selected else 0.0,
            },
            "artifact_dir": str(artifact_dir),
            "artifact_paths": [str(artifact_dir / "result.json")],
            "workspace_root": "training",
            "next_command": "d5 training rehearsal --json",
        }
        write_json_artifact(
            artifact_dir / "result.json",
            result,
            owner_type="training_experiment_batch_result",
            owner_key=result_id,
            artifact_type="training_experiment_batch_result",
            settings=self.settings,
        )
        return result

    def rehearsal(self) -> dict[str, Any]:
        """Run a full scratch training-evolution rehearsal without canonical mutation."""
        rehearsal_id = f"training_rehearsal_{uuid.uuid4().hex[:12]}"
        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "training"
            / "rehearsals"
            / rehearsal_id
        )
        paths = _RehearsalPaths(
            artifact_dir=artifact_dir,
            scratch_repo_root=artifact_dir / "scratch_repo",
            scratch_data_dir=artifact_dir / "scratch_data",
            scratch_db_path=artifact_dir / "scratch_data" / "db" / "d5.db",
            scratch_duckdb_path=artifact_dir / "scratch_data" / "db" / "d5_analytics.duckdb",
            scratch_coinbase_raw_db_path=artifact_dir / "scratch_data" / "db" / "coinbase_raw.db",
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        scratch_settings = _scratch_settings(self.settings, paths)

        reset_engine()
        try:
            run_migrations_to_head(scratch_settings)
            self._seed_rehearsal_fixture(scratch_settings, rehearsal_id)
            scratch_runtime = TrainingRuntime(scratch_settings)
            evidence_rollup = scratch_runtime.evidence_rollup()
            experiment_batch = scratch_runtime.experiment_batch()
            proposal_ids = [
                str(candidate["proposal_id"])
                for candidate in experiment_batch.get("candidates", [])
                if candidate.get("proposal_id")
            ]
            batch_review = scratch_runtime.review_batch(proposal_ids=proposal_ids)
            comparison = ProposalComparator(scratch_settings).compare_proposals(
                proposal_ids=proposal_ids,
                proposal_kind="candidate_overlay_experiment",
                choose_top=True,
            )
            selected_proposal_id = str(comparison.get("selected_proposal_id") or "")
            if not selected_proposal_id and proposal_ids:
                selected_proposal_id = proposal_ids[0]
            experiment_result = scratch_runtime.run_experiment_batch(
                selected_proposal_id=selected_proposal_id,
            )
            evolution = self._apply_rehearsal_paper_evolution(
                scratch_settings,
                rehearsal_id=rehearsal_id,
                selected_proposal_id=selected_proposal_id,
                comparison_id=str(comparison.get("comparison_id") or ""),
            )
            paper_practice = self._seed_rehearsal_paper_trade(
                scratch_settings,
                rehearsal_id=rehearsal_id,
                evolved_revision_id=evolution["active_profile_revision_id"],
            )
            ledger = self._write_rehearsal_ledger(
                scratch_settings,
                artifact_dir=artifact_dir,
            )
        finally:
            reset_engine()

        summary = {
            "status": "completed",
            "mode": "scratch_rehearsal",
            "run_id": rehearsal_id,
            "artifact_dir": str(artifact_dir),
            "summary_path": str(artifact_dir / "summary.json"),
            "workspace_root": "training",
            "canonical_db_path": str(self.settings.db_path),
            "scratch_db_path": str(paths.scratch_db_path),
            "scratch_paths": {
                "artifact_dir": str(paths.artifact_dir),
                "scratch_repo_root": str(paths.scratch_repo_root),
                "scratch_data_dir": str(paths.scratch_data_dir),
                "scratch_db_path": str(paths.scratch_db_path),
                "scratch_duckdb_path": str(paths.scratch_duckdb_path),
                "scratch_coinbase_raw_db_path": str(paths.scratch_coinbase_raw_db_path),
            },
            "authority": {
                "live_trading_allowed": False,
                "wallet_required": False,
                "canonical_runtime_mutated": False,
                "runtime_effect": "paper_research_rehearsal_only",
            },
            "evidence_rollup": evidence_rollup,
            "experiment_batch": {
                "run_id": experiment_batch.get("run_id", ""),
                "selected_batch_type": experiment_batch.get("selected_batch_type", ""),
                "candidate_count": experiment_batch.get("candidate_count", 0),
                "candidate_proposal_ids": proposal_ids,
            },
            "batch_review": {
                "review_count": batch_review["review_count"],
                "eligible_review_count": batch_review["eligible_review_count"],
            },
            "comparison": comparison,
            "experiment_result": experiment_result,
            "evolution": evolution,
            "paper_practice": paper_practice,
            "ledger": ledger,
            "artifact_paths": [
                str(artifact_dir / "summary.json"),
                str(artifact_dir / "report.qmd"),
                ledger["csv_path"],
                *([ledger["parquet_path"]] if ledger.get("parquet_path") else []),
            ],
            "next_command": "d5 training status --json",
        }
        (artifact_dir / "summary.json").write_bytes(
            orjson.dumps(summary, option=orjson.OPT_INDENT_2)
        )
        (artifact_dir / "report.qmd").write_text(
            render_qmd(
                "experiment_run.qmd",
                title="training evolution rehearsal",
                metadata=trading_report_metadata(
                    report_kind="training_rehearsal",
                    run_id=rehearsal_id,
                    owner_type="training_rehearsal",
                    owner_key=rehearsal_id,
                    profile_revision_id=evolution["active_profile_revision_id"],
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="synthetic_fixture",
                    summary_path="summary.json",
                    config_path="summary.json",
                ),
                summary_lines=[
                    f"- rehearsal id: `{rehearsal_id}`",
                    f"- scratch db: `{paths.scratch_db_path}`",
                    f"- selected batch: `{experiment_batch.get('selected_batch_type', '')}`",
                    f"- selected proposal: `{selected_proposal_id or 'none'}`",
                    f"- evolution happened: `{evolution['evolution_happened']}`",
                    f"- completed trades: `{paper_practice['completed_trades']}`",
                    f"- win rate: `{paper_practice['win_rate']}`",
                    "- authority: `paper/research only; no live order routing`",
                ],
                sections=[
                    (
                        "Ledger",
                        [
                            f"- csv: `{ledger['csv_path']}`",
                            f"- parquet: `{ledger.get('parquet_path') or 'not written'}`",
                        ],
                    )
                ],
                generated_at=utcnow(),
            ),
            encoding="utf-8",
        )
        return summary

    def _seed_rehearsal_fixture(self, settings: Settings, rehearsal_id: str) -> None:
        """Seed no-trade evidence that forces the learning loop to select a candidate."""
        now = utcnow()
        session = get_session(settings)
        try:
            profile = PaperPracticeProfileV1(
                profile_id=f"{rehearsal_id}_profile",
                status="active",
                active_revision_id=None,
                instrument_pair="SOL/USDC",
                context_anchors_json="[]",
                cadence_minutes=15,
                max_open_sessions=1,
                created_at=now,
                updated_at=now,
            )
            session.add(profile)
            session.flush()
            revision = PaperPracticeProfileRevisionV1(
                revision_id=f"{rehearsal_id}_revision_001",
                profile_id=profile.profile_id,
                revision_index=1,
                status="active",
                mutation_source="rehearsal_seed",
                applied_parameter_json=orjson.dumps(
                    {
                        "minimum_condition_confidence": 0.72,
                        "preferred_family": "none",
                    }
                ).decode(),
                allowed_mutation_keys_json=orjson.dumps(
                    [
                        "preferred_family",
                        "minimum_condition_confidence",
                        "stop_loss_bps",
                        "take_profit_bps",
                        "cooldown_bars",
                    ]
                ).decode(),
                summary="Synthetic baseline profile before evidence-backed rehearsal evolution.",
                created_at=now,
            )
            session.add(revision)
            session.flush()
            profile.active_revision_id = revision.revision_id
            loop = PaperPracticeLoopRunV1(
                loop_run_id=f"{rehearsal_id}_loop_seed",
                mode="scratch_rehearsal",
                status="completed",
                active_profile_id=profile.profile_id,
                active_revision_id=revision.revision_id,
                with_helius_ws=0,
                max_iterations=2,
                iterations_completed=2,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
            session.add(loop)
            session.flush()
            for index, reason_code in enumerate(
                (
                    "strategy_target_not_runtime_long:flat",
                    "strategy_regime_not_allowed:long_friendly",
                ),
                start=1,
            ):
                session.add(
                    PaperPracticeDecisionV1(
                        decision_id=f"{rehearsal_id}_decision_no_trade_{index}",
                        loop_run_id=loop.loop_run_id,
                        profile_id=profile.profile_id,
                        profile_revision_id=revision.revision_id,
                        decision_type="no_trade",
                        decision_payload_json=orjson.dumps(
                            {
                                "rehearsal_phase": "baseline",
                                "market_regime": "long_friendly",
                                "feature_valid": True,
                                "strategy_candidate": False,
                                "policy_allowed": False,
                                "risk_approved": False,
                                "paper_trade_opened": False,
                            }
                        ).decode(),
                        reason_codes_json=orjson.dumps([reason_code]).decode(),
                        created_at=now,
                    )
                )
            session.commit()
        finally:
            session.close()

    def _apply_rehearsal_paper_evolution(
        self,
        settings: Settings,
        *,
        rehearsal_id: str,
        selected_proposal_id: str,
        comparison_id: str,
    ) -> dict[str, Any]:
        now = utcnow()
        session = get_session(settings)
        try:
            profile = (
                session.query(PaperPracticeProfileV1)
                .filter(PaperPracticeProfileV1.status == "active")
                .order_by(PaperPracticeProfileV1.id.desc())
                .first()
            )
            if profile is None:
                raise RuntimeError("rehearsal profile missing")
            latest_revision = (
                session.query(PaperPracticeProfileRevisionV1)
                .filter_by(profile_id=profile.profile_id)
                .order_by(PaperPracticeProfileRevisionV1.revision_index.desc())
                .first()
            )
            next_index = (latest_revision.revision_index if latest_revision else 0) + 1
            applied = {
                "preferred_family": "trend_continuation_long_v1",
                "minimum_condition_confidence": 0.55,
                "stop_loss_bps": 75,
                "take_profit_bps": 140,
                "cooldown_bars": 1,
            }
            evolved_revision = PaperPracticeProfileRevisionV1(
                revision_id=f"{rehearsal_id}_revision_{next_index:03d}",
                profile_id=profile.profile_id,
                revision_index=next_index,
                status="active",
                mutation_source="training_rehearsal_candidate_overlay",
                source_proposal_id=selected_proposal_id or None,
                source_comparison_id=comparison_id or None,
                applied_parameter_json=orjson.dumps(applied).decode(),
                allowed_mutation_keys_json=orjson.dumps(sorted(applied)).decode(),
                summary=(
                    "Applied bounded paper-profile overlay after scratch evidence "
                    "selected a candidate experiment. No runtime policy or risk files changed."
                ),
                created_at=now,
            )
            session.add(evolved_revision)
            session.flush()
            profile.active_revision_id = evolved_revision.revision_id
            profile.updated_at = now
            session.commit()
            return {
                "evolution_happened": True,
                "mutation_surface": "paper_profile_revision",
                "active_profile_id": profile.profile_id,
                "active_profile_revision_id": evolved_revision.revision_id,
                "source_proposal_id": selected_proposal_id,
                "source_comparison_id": comparison_id,
                "applied_parameter_patch": applied,
                "blocked_reason": "",
            }
        finally:
            session.close()

    def _seed_rehearsal_paper_trade(
        self,
        settings: Settings,
        *,
        rehearsal_id: str,
        evolved_revision_id: str,
    ) -> dict[str, Any]:
        now = utcnow()
        session = get_session(settings)
        try:
            profile = (
                session.query(PaperPracticeProfileV1)
                .filter(PaperPracticeProfileV1.active_revision_id == evolved_revision_id)
                .one()
            )
            loop = PaperPracticeLoopRunV1(
                loop_run_id=f"{rehearsal_id}_loop_evolved",
                mode="scratch_rehearsal",
                status="completed",
                active_profile_id=profile.profile_id,
                active_revision_id=evolved_revision_id,
                with_helius_ws=0,
                max_iterations=2,
                iterations_completed=2,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
            session.add(loop)
            session.flush()
            session_key = f"{rehearsal_id}_paper_session_001"
            decisions = [
                (
                    "paper_trade_opened",
                    "paper_trade_opened",
                    {
                        "rehearsal_phase": "evolved_profile",
                        "market_regime": "long_friendly",
                        "feature_valid": True,
                        "strategy_candidate": True,
                        "policy_allowed": True,
                        "risk_approved": True,
                        "paper_trade_opened": True,
                        "paper_trade_closed": False,
                        "pnl_usdc": 0.0,
                    },
                ),
                (
                    "paper_trade_closed",
                    "paper_trade_closed_profit",
                    {
                        "rehearsal_phase": "evolved_profile",
                        "market_regime": "long_friendly",
                        "feature_valid": True,
                        "strategy_candidate": True,
                        "policy_allowed": True,
                        "risk_approved": True,
                        "paper_trade_opened": True,
                        "paper_trade_closed": True,
                        "pnl_usdc": 1.25,
                    },
                ),
            ]
            for index, (decision_type, reason_code, payload) in enumerate(decisions, start=1):
                session.add(
                    PaperPracticeDecisionV1(
                        decision_id=f"{rehearsal_id}_decision_evolved_{index}",
                        loop_run_id=loop.loop_run_id,
                        profile_id=profile.profile_id,
                        profile_revision_id=evolved_revision_id,
                        decision_type=decision_type,
                        session_key=session_key,
                        decision_payload_json=orjson.dumps(payload).decode(),
                        reason_codes_json=orjson.dumps([reason_code]).decode(),
                        created_at=now,
                    )
                )
            session.commit()
            return {
                "trade_count": 1,
                "completed_trades": 1,
                "wins": 1,
                "losses": 0,
                "win_rate": 1.0,
                "realized_pnl_usdc": 1.25,
                "profit_factor": 999.0,
                "session_key": session_key,
            }
        finally:
            session.close()

    def _write_rehearsal_ledger(
        self,
        settings: Settings,
        *,
        artifact_dir: Path,
    ) -> dict[str, Any]:
        ledger_dir = artifact_dir / "ledger"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        csv_path = ledger_dir / "ledger.csv"
        parquet_path = ledger_dir / "ledger.parquet"
        session = get_session(settings)
        try:
            decisions = (
                session.query(PaperPracticeDecisionV1)
                .order_by(PaperPracticeDecisionV1.created_at.asc(), PaperPracticeDecisionV1.id.asc())
                .all()
            )
            rows: list[dict[str, Any]] = []
            for decision in decisions:
                payload = _load_json_object(decision.decision_payload_json)
                reason_codes = _load_json_list(decision.reason_codes_json)
                rows.append(
                    {
                        "created_at": decision.created_at.isoformat(),
                        "loop_run_id": decision.loop_run_id,
                        "profile_id": decision.profile_id,
                        "profile_revision_id": decision.profile_revision_id,
                        "decision_type": decision.decision_type,
                        "session_key": decision.session_key or "",
                        "market_regime": payload.get("market_regime", ""),
                        "feature_valid": payload.get("feature_valid", ""),
                        "strategy_candidate": payload.get("strategy_candidate", ""),
                        "policy_allowed": payload.get("policy_allowed", ""),
                        "risk_approved": payload.get("risk_approved", ""),
                        "paper_trade_opened": payload.get("paper_trade_opened", ""),
                        "paper_trade_closed": payload.get("paper_trade_closed", ""),
                        "pnl_usdc": payload.get("pnl_usdc", ""),
                        "reason_codes": "|".join(reason_codes),
                    }
                )
        finally:
            session.close()

        fieldnames = [
            "created_at",
            "loop_run_id",
            "profile_id",
            "profile_revision_id",
            "decision_type",
            "session_key",
            "market_regime",
            "feature_valid",
            "strategy_candidate",
            "policy_allowed",
            "risk_approved",
            "paper_trade_opened",
            "paper_trade_closed",
            "pnl_usdc",
            "reason_codes",
        ]
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        parquet_written = False
        try:
            import pandas as pd  # type: ignore

            pd.DataFrame(rows).to_parquet(parquet_path, index=False)
            parquet_written = True
        except Exception:
            parquet_path = Path("")

        no_trade_count = sum(1 for row in rows if row["decision_type"] == "no_trade")
        completed_trades = sum(1 for row in rows if row["decision_type"] == "paper_trade_closed")
        return {
            "csv_path": str(csv_path),
            "parquet_path": str(parquet_path) if parquet_written else "",
            "row_count": len(rows),
            "no_trade_count": no_trade_count,
            "completed_trades": completed_trades,
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
                            "- workspace root: `training/`",
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
