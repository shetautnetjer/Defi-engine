from __future__ import annotations

import json
from pathlib import Path

import orjson

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.research_loop.training_runtime import (
    TrainingRuntime,
    _merge_historical_cache_status,
    _merge_training_status,
    _summarize_governor_status,
    _summarize_trader_lane_status,
)
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ImprovementProposalV1,
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
    PaperPracticeProfileRevisionV1,
    PaperPracticeProfileV1,
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


def test_merge_training_status_prefers_terminal_db_status_over_stale_running_receipt() -> None:
    db_status = {
        "latest_loop_run_id": "loop_shared",
        "latest_loop_status": "completed",
        "latest_decision_id": "decision_db",
    }
    status_receipt = {
        "loop_state": {
            "loop_run_id": "loop_shared",
            "status": "running",
            "latest_decision_id": "decision_receipt",
            "latest_session_key": "paper_session_1",
        }
    }

    merged = _merge_training_status(db_status, status_receipt)

    assert merged["effective_loop_run_id"] == "loop_shared"
    assert merged["effective_loop_status"] == "completed"
    assert merged["effective_latest_decision_id"] == "decision_receipt"
    assert merged["effective_latest_session_key"] == "paper_session_1"
    assert len(merged["status_conflicts"]) == 1


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


def test_training_evidence_gap_ranks_no_trade_failure_families(settings) -> None:
    run_migrations_to_head(settings)
    now = utcnow()
    session = get_session(settings)
    try:
        profile = PaperPracticeProfileV1(
            profile_id="paper_practice_profile_test",
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
        session.add(
            PaperPracticeProfileRevisionV1(
                revision_id="paper_practice_revision_test",
                profile_id="paper_practice_profile_test",
                revision_index=1,
                status="active",
                mutation_source="bootstrap",
                applied_parameter_json="{}",
                allowed_mutation_keys_json="[]",
                summary="test revision",
                created_at=now,
            )
        )
        session.flush()
        profile.active_revision_id = "paper_practice_revision_test"
        session.flush()
        session.add(
            PaperPracticeLoopRunV1(
                loop_run_id="paper_practice_loop_test",
                mode="bounded",
                status="completed",
                active_profile_id="paper_practice_profile_test",
                active_revision_id="paper_practice_revision_test",
                with_helius_ws=0,
                max_iterations=3,
                iterations_completed=3,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.flush()
        session.add_all(
            [
                PaperPracticeDecisionV1(
                    decision_id="decision_strategy_mismatch",
                    loop_run_id="paper_practice_loop_test",
                    profile_id="paper_practice_profile_test",
                    profile_revision_id="paper_practice_revision_test",
                    decision_type="no_trade",
                    decision_payload_json=orjson.dumps(
                        {
                            "evidence_feedback": {
                                "primary_failure_surface": "strategy_runtime_mismatch",
                                "candidate_overlay_type": "candidate_strategy_policy_overlay_v1",
                            }
                        }
                    ).decode(),
                    reason_codes_json=orjson.dumps(
                        ["strategy_target_not_runtime_long:down"]
                    ).decode(),
                    created_at=now,
                ),
                PaperPracticeDecisionV1(
                    decision_id="decision_confidence",
                    loop_run_id="paper_practice_loop_test",
                    profile_id="paper_practice_profile_test",
                    profile_revision_id="paper_practice_revision_test",
                    decision_type="no_trade",
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(
                        ["condition_confidence_below_profile_minimum"]
                    ).decode(),
                    created_at=now,
                ),
                PaperPracticeDecisionV1(
                    decision_id="decision_trade_opened",
                    loop_run_id="paper_practice_loop_test",
                    profile_id="paper_practice_profile_test",
                    profile_revision_id="paper_practice_revision_test",
                    decision_type="paper_trade_opened",
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(["paper_trade_opened"]).decode(),
                    created_at=now,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = TrainingRuntime(settings).evidence_gap()

    assert (
        result["primary_learning_gap"]
        == "proposals_not_being_converted_to_comparable_tests"
    )
    assert result["selected_batch_type"] == "strategy_runtime_mismatch_batch"
    assert result["recommended_batch_type"] == "strategy_runtime_mismatch_batch"
    assert result["top_failure_families"][0]["family"] == "strategy_runtime_mismatch"
    assert (
        result["top_reason_codes"][0]["reason_code"]
        == "strategy_target_not_runtime_long:down"
    )
    assert result["decision_funnel"]["decision_cycles"] == 3
    assert result["decision_funnel"]["no_trade_cycles"] == 2


def test_training_experiment_batch_writes_candidate_overlays(settings) -> None:
    run_migrations_to_head(settings)
    now = utcnow()
    session = get_session(settings)
    try:
        profile = PaperPracticeProfileV1(
            profile_id="paper_practice_profile_batch",
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
        session.add(
            PaperPracticeProfileRevisionV1(
                revision_id="paper_practice_revision_batch",
                profile_id="paper_practice_profile_batch",
                revision_index=1,
                status="active",
                mutation_source="bootstrap",
                applied_parameter_json="{}",
                allowed_mutation_keys_json="[]",
                summary="batch revision",
                created_at=now,
            )
        )
        session.flush()
        profile.active_revision_id = "paper_practice_revision_batch"
        session.add(
            PaperPracticeLoopRunV1(
                loop_run_id="paper_practice_loop_batch",
                mode="bounded",
                status="completed",
                active_profile_id="paper_practice_profile_batch",
                active_revision_id="paper_practice_revision_batch",
                with_helius_ws=0,
                max_iterations=2,
                iterations_completed=2,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.flush()
        session.add_all(
            [
                PaperPracticeDecisionV1(
                    decision_id="decision_batch_strategy_mismatch",
                    loop_run_id="paper_practice_loop_batch",
                    profile_id="paper_practice_profile_batch",
                    profile_revision_id="paper_practice_revision_batch",
                    decision_type="no_trade",
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(
                        ["strategy_target_not_runtime_long:flat"]
                    ).decode(),
                    created_at=now,
                ),
                PaperPracticeDecisionV1(
                    decision_id="decision_batch_policy_mismatch",
                    loop_run_id="paper_practice_loop_batch",
                    profile_id="paper_practice_profile_batch",
                    profile_revision_id="paper_practice_revision_batch",
                    decision_type="no_trade",
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(
                        ["strategy_regime_not_allowed:long_friendly"]
                    ).decode(),
                    created_at=now,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    result = TrainingRuntime(settings).experiment_batch()

    assert result["selected_failure_family"] == "strategy_runtime_mismatch"
    assert result["selected_batch_type"] == "strategy_runtime_mismatch_batch"
    assert result["candidate_count"] == 3
    assert result["falsification_candidate_included"] is True
    assert {
        candidate["candidate_overlay_type"] for candidate in result["candidates"]
    } >= {
        "candidate_strategy_policy_overlay_v1",
        "candidate_policy_overlay_v1",
    }
    assert (Path(result["artifact_dir"]) / "batch.json").exists()
    assert (Path(result["artifact_dir"]) / "batch_selection.json").exists()
    assert result["next_command"] == "d5 training review-batch --batch latest --json"


def test_training_rehearsal_runs_isolated_evolution_loop(settings) -> None:
    run_migrations_to_head(settings)

    result = TrainingRuntime(settings).rehearsal()

    assert result["status"] == "completed"
    assert result["mode"] == "scratch_rehearsal"
    assert result["canonical_db_path"] == str(settings.db_path)
    assert result["scratch_db_path"] != str(settings.db_path)
    assert result["authority"]["live_trading_allowed"] is False
    assert result["authority"]["canonical_runtime_mutated"] is False
    assert result["evolution"]["evolution_happened"] is True
    assert result["evolution"]["mutation_surface"] == "paper_profile_revision"
    assert result["paper_practice"]["completed_trades"] >= 1
    assert result["paper_practice"]["win_rate"] >= 0.5

    ledger_csv = Path(result["ledger"]["csv_path"])
    assert ledger_csv.exists()
    ledger_text = ledger_csv.read_text(encoding="utf-8")
    assert "decision_type" in ledger_text
    assert "paper_trade_closed" in ledger_text
    assert Path(result["summary_path"]).exists()
    assert Path(result["artifact_dir"]).is_relative_to(settings.data_dir)

    session = get_session(settings)
    try:
        assert session.query(PaperPracticeDecisionV1).count() == 0
        assert session.query(ImprovementProposalV1).count() == 0
        assert session.query(PaperPracticeProfileRevisionV1).count() == 0
    finally:
        session.close()


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
            "completed_day_count": 0,
            "capture_completed_day_count": 335,
            "capture_missing_day_count": 395,
            "capture_next_missing_date": "2025-03-20",
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


def test_training_status_prefers_loop_after_historical_ladder_completed(
    settings,
    monkeypatch,
) -> None:
    runtime = TrainingRuntime(settings)
    state_root = settings.repo_root / ".ai" / "dropbox" / "state"
    state_root.mkdir(parents=True, exist_ok=True)
    (state_root / "paper_practice_status.json").write_text(
        json.dumps({"loop_state": {"historical_ladder_completed": True, "status": "completed"}})
    )

    monkeypatch.setattr(
        runtime.practice,
        "get_status",
        lambda: {
            "active_profile_id": "paper_profile_test",
            "active_revision_id": "paper_profile_revision_test",
            "profile_payload": {"instrument_pair": "SOL/USDC"},
            "selected_training_profile": {"name": "quickstart_300d", "ready": True},
            "training_profile_readiness": {
                "selected_profile_name": "quickstart_300d",
                "profiles": {},
            },
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
            "completed_day_count": 0,
            "capture_completed_day_count": 340,
            "missing_day_count": 390,
            "next_missing_date": "2025-03-25",
        },
    )

    status = runtime.status()

    assert status["next_command"] == "d5 training loop --json"
