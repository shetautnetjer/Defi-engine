from __future__ import annotations

import json

from d5_trading_engine.research_loop.training_runtime import (
    TrainingRuntime,
    _summarize_governor_status,
    _merge_historical_cache_status,
    _merge_training_status,
    _summarize_trader_lane_status,
)


def test_merge_historical_cache_status_exposes_capture_and_warehouse_surfaces() -> None:
    warehouse = {
        "complete": False,
        "completed_day_count": 0,
        "missing_day_count": 730,
        "next_missing_date": "2024-04-19",
    }
    latest_source_collection = {
        "historical_cache_after": {
            "complete": False,
            "completed_day_count": 316,
            "missing_day_count": 414,
            "next_missing_date": "2025-03-01",
            "latest_completed_date": "2025-02-28",
        }
    }

    merged = _merge_historical_cache_status(warehouse, latest_source_collection)

    assert merged["completed_day_count"] == 0
    assert merged["completeness_basis"] == "warehouse(raw+parquet+sql)"
    assert merged["capture_completed_day_count"] == 316
    assert merged["capture_missing_day_count"] == 414
    assert merged["capture_next_missing_date"] == "2025-03-01"


def test_merge_training_status_prefers_runtime_receipt_and_records_conflicts() -> None:
    db_status = {
        "latest_loop_run_id": "loop_db",
        "latest_loop_status": "completed",
        "latest_decision_id": "decision_db",
    }
    status_receipt = {
        "loop_state": {
            "loop_run_id": "loop_receipt",
            "status": "running",
            "latest_decision_id": "decision_receipt",
            "latest_session_key": "paper_session_1",
        }
    }

    merged = _merge_training_status(db_status, status_receipt)

    assert merged["effective_loop_run_id"] == "loop_receipt"
    assert merged["effective_loop_status"] == "running"
    assert merged["effective_latest_decision_id"] == "decision_receipt"
    assert merged["effective_latest_session_key"] == "paper_session_1"
    assert len(merged["status_conflicts"]) == 2


def test_summarize_trader_lane_status_combines_lane_and_watcher_surfaces() -> None:
    lane_sessions = {
        "trader": {
            "lane_name": "trader",
            "mode": "persistent",
            "profile": "trader",
            "session_id": "sess-1",
            "thread_id": "thread-1",
            "last_event_id": "evt-1",
            "updated_at_utc": "2026-04-19T13:00:00Z",
            "stale_after_hours": 24,
        }
    }
    watcher_status = {
        "status": "once_complete",
        "last_event_id": "evt-1",
        "last_dispatch_ok": True,
    }

    summary = _summarize_trader_lane_status(lane_sessions, watcher_status)

    assert summary["present"] is True
    assert summary["session_id"] == "sess-1"
    assert summary["watcher_status"] == "once_complete"
    assert summary["watcher_last_dispatch_ok"] is True


def test_summarize_governor_status_reads_latest_review_and_priority_receipts() -> None:
    review_receipt = {
        "review_id": "review_1",
        "governor_policy_id": "profile_router_policy_v1",
        "governor_action": "SHADOW_ONLY",
        "updated_at": "2026-04-19T13:00:00Z",
    }
    priority_receipt = {
        "comparison_id": "comparison_1",
        "governor_policy_id": "profile_router_policy_v1",
        "governor_action": "SELECT_PROFILE",
        "updated_at": "2026-04-19T13:05:00Z",
    }

    summary = _summarize_governor_status(review_receipt, priority_receipt)

    assert summary["policy_id"] == "profile_router_policy_v1"
    assert summary["latest_action"] == "SELECT_PROFILE"
    assert summary["latest_review_action"] == "SHADOW_ONLY"
    assert summary["latest_priority_action"] == "SELECT_PROFILE"


def test_training_status_prefers_bootstrap_when_selected_regimen_is_ready(
    settings,
    monkeypatch,
) -> None:
    runtime = TrainingRuntime(settings)
    state_root = settings.repo_root / ".ai" / "dropbox" / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    (state_root / "paper_practice_status.json").write_text(json.dumps({"loop_state": {}}))
    (state_root / "research_proposal_review_receipt.json").write_text(
        json.dumps(
            {
                "review_id": "review_fixture",
                "governor_policy_id": "profile_router_policy_v1",
                "governor_action": "SHADOW_ONLY",
                "updated_at": "2026-04-19T12:00:00Z",
            }
        )
    )
    (state_root / "research_proposal_priority_receipt.json").write_text(
        json.dumps(
            {
                "comparison_id": "comparison_fixture",
                "governor_policy_id": "profile_router_policy_v1",
                "governor_action": "SELECT_PROFILE",
                "updated_at": "2026-04-19T12:05:00Z",
            }
        )
    )

    monkeypatch.setattr(
        runtime.practice,
        "get_status",
        lambda: {
            "active_profile_id": "paper_profile_test",
            "active_revision_id": "paper_profile_revision_test",
            "profile_payload": {"instrument_pair": "SOL/USDC"},
            "selected_training_profile": {"name": "quickstart_300d", "ready": True},
            "training_profile_readiness": {"selected_profile_name": "quickstart_300d", "profiles": {}},
            "open_session_key": "",
            "open_session_status": "",
            "latest_loop_run_id": "",
            "latest_loop_status": "",
            "latest_decision_id": "",
            "latest_decision_type": "",
        },
    )
    monkeypatch.setattr(
        runtime.practice,
        "historical_cache_status",
        lambda: {
            "complete": False,
            "completed_day_count": 335,
            "missing_day_count": 395,
            "next_missing_date": "2025-03-20",
        },
    )

    status = runtime.status()

    assert status["selected_training_profile"]["name"] == "quickstart_300d"
    assert status["selected_training_regimen"]["name"] == "quickstart_300d"
    assert status["selected_research_profile"]["name"] == "execution_cost_minimizer"
    assert "execution / intraday" in status["selected_research_profile_summary"]
    assert status["next_command"] == "d5 training bootstrap --json"
    assert status["training_regimen_readiness"]["selected_profile_name"] == "quickstart_300d"
    assert status["governor_status"]["policy_id"] == "profile_router_policy_v1"
    assert status["governor_status"]["latest_action"] == "SELECT_PROFILE"
