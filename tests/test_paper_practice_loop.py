from __future__ import annotations

import json

import pandas as pd
import pytest

from d5_trading_engine.capture.massive_backfill import MassiveMinuteAggsBackfill
from d5_trading_engine.common.errors import FeatureError
from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
    PaperPracticeProfileRevisionV1,
    PaperPracticeProfileV1,
)
from tests.test_backtest_walk_forward import _seed_strategy_report
from tests.test_label_strategy_loop import _seed_research_repo_truth
from tests.test_paper_runtime_operator import _seed_condition_run
from tests.test_settlement_paper import _seed_quote_snapshot, _tracked_mint


def test_ensure_active_profile_creates_sql_overlay_and_receipt(settings) -> None:
    run_migrations_to_head(settings)

    runtime = PaperPracticeRuntime(settings)
    profile = runtime.ensure_active_profile()

    assert profile["profile_id"].startswith("paper_profile_")
    assert profile["active_revision_id"].startswith("paper_profile_revision_")
    assert profile["payload"]["instrument_pair"] == "SOL/USDC"

    session = get_session(settings)
    try:
        assert session.query(PaperPracticeProfileV1).count() == 1
        assert session.query(PaperPracticeProfileRevisionV1).count() == 1
    finally:
        session.close()

    receipt_path = (
        settings.repo_root
        / ".ai"
        / "dropbox"
        / "state"
        / "paper_practice_latest_profile_revision.json"
    )
    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["profile_id"] == profile["profile_id"]
    assert payload["active_revision_id"] == profile["active_revision_id"]


def test_paper_practice_loop_max_iterations_one_records_open_decision(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    _seed_strategy_report(settings)
    condition_run_id = _seed_condition_run(
        settings,
        run_id="condition_practice_loop",
        semantic_regime="long_friendly",
    )
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_practice_loop",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )

    async def _fake_live_cycle(self, *, with_helius_ws=False):
        return {
            "cycle_id": "live_cycle_test",
            "quote_snapshot_id": quote_snapshot_id,
            "condition_run_id": condition_run_id,
            "ready_for_paper_cycle": True,
            "risk_state": "allowed",
        }

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.live_regime_cycle.LiveRegimeCycleRunner.run_live_regime_cycle",
        _fake_live_cycle,
    )
    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.operator.PaperTradeOperator.run_cycle",
        lambda self, **kwargs: {
            "session_key": "paper_session_test",
            "session_status": "open",
            "filled": True,
            "policy_result": {"trace_id": None, "policy_state": "eligible_long"},
            "risk_result": {"risk_verdict_id": None, "risk_state": "allowed"},
        },
    )
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_ensure_historical_ladder_completed",
        lambda self: {"bootstrap_id": "paper_practice_bootstrap_test", "completed_ladder": True},
    )
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_load_profile_strategy_selection",
        lambda self, payload: {
            "top_family": "trend_continuation_long_v1",
            "target_label": "up",
            "allowed_regimes": ["long_friendly"],
        },
    )

    runtime = PaperPracticeRuntime(settings)
    result = runtime.run_loop(max_iterations=1)

    assert result["status"] == "completed"
    assert result["iterations_completed"] == 1

    session = get_session(settings)
    try:
        loop_run = session.query(PaperPracticeLoopRunV1).one()
        decision = session.query(PaperPracticeDecisionV1).one()
    finally:
        session.close()

    assert loop_run.status == "completed"
    assert decision.decision_type == "paper_trade_opened"
    assert decision.session_key == "paper_session_test"

    status_receipt = json.loads(
        (
            settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "paper_practice_status.json"
        ).read_text(encoding="utf-8")
    )
    assert status_receipt["loop_state"]["status"] == "completed"
    assert status_receipt["loop_state"]["historical_ladder_completed"] is True


def test_paper_practice_loop_turns_no_trade_reason_into_evidence_feedback(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    _seed_strategy_report(settings)
    condition_run_id = _seed_condition_run(
        settings,
        run_id="condition_no_trade_feedback",
        semantic_regime="long_friendly",
    )
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_no_trade_feedback",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )

    async def _fake_live_cycle(self, *, with_helius_ws=False):
        return {
            "cycle_id": "live_cycle_no_trade_feedback",
            "quote_snapshot_id": quote_snapshot_id,
            "condition_run_id": condition_run_id,
            "ready_for_paper_cycle": True,
            "risk_state": "allowed",
        }

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.live_regime_cycle.LiveRegimeCycleRunner.run_live_regime_cycle",
        _fake_live_cycle,
    )
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_ensure_historical_ladder_completed",
        lambda self: {"bootstrap_id": "paper_practice_bootstrap_test", "completed_ladder": True},
    )
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_load_profile_strategy_selection",
        lambda self, payload: {
            "top_family": "mean_reversion_short_v1",
            "target_label": "down",
            "allowed_regimes": ["long_friendly"],
        },
    )

    runtime = PaperPracticeRuntime(settings)
    result = runtime.run_loop(max_iterations=1)

    assert result["status"] == "completed"

    session = get_session(settings)
    try:
        decision = session.query(PaperPracticeDecisionV1).one()
        decision_payload = json.loads(decision.decision_payload_json)
        reason_codes = json.loads(decision.reason_codes_json)
    finally:
        session.close()

    assert decision.decision_type == "no_trade"
    assert "strategy_target_not_runtime_long:down" in reason_codes
    feedback = decision_payload["evidence_feedback"]
    assert feedback["primary_failure_surface"] == "strategy_runtime_mismatch"
    assert feedback["candidate_overlay_type"] == "candidate_strategy_policy_overlay_v1"
    assert feedback["recommended_next_command"] == "d5 run-strategy-eval governed-challengers-v1 --json"

    feedback_receipt = json.loads(
        (
            settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "paper_practice_latest_evidence_feedback.json"
        ).read_text(encoding="utf-8")
    )
    assert feedback_receipt["decision_type"] == "no_trade"
    assert feedback_receipt["evidence_feedback"]["primary_failure_surface"] == "strategy_runtime_mismatch"


def test_paper_practice_loop_records_abort_decision_on_freshness_failure(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)

    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_ensure_historical_ladder_completed",
        lambda self: {"bootstrap_id": "paper_practice_bootstrap_test", "completed_ladder": True},
    )

    def _raise_freshness_failure(self, *, loop_run_id: str, with_helius_ws: bool):
        raise FeatureError("Freshness authorization failed: fred-observations=degraded")

    monkeypatch.setattr(PaperPracticeRuntime, "_run_iteration", _raise_freshness_failure)

    runtime = PaperPracticeRuntime(settings)
    with pytest.raises(FeatureError):
        runtime.run_loop(max_iterations=1)

    session = get_session(settings)
    try:
        loop_run = session.query(PaperPracticeLoopRunV1).one()
        decision = session.query(PaperPracticeDecisionV1).one()
        decision_payload = json.loads(decision.decision_payload_json)
        reason_codes = json.loads(decision.reason_codes_json)
    finally:
        session.close()

    assert loop_run.status == "failed"
    assert loop_run.latest_decision_id == decision.decision_id
    assert decision.decision_type == "no_trade"
    assert "paper_loop_abort" in reason_codes
    assert "freshness_authorization_failed" in reason_codes
    assert "source_freshness_block:fred-observations" in reason_codes
    assert (
        decision_payload["evidence_feedback"]["primary_failure_surface"]
        == "feature_materialization_gap"
    )
    assert (
        decision_payload["error_message"]
        == "Freshness authorization failed: fred-observations=degraded"
    )

    status_receipt = json.loads(
        (
            settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "paper_practice_status.json"
        ).read_text(encoding="utf-8")
    )
    assert status_receipt["loop_state"]["status"] == "failed"
    assert status_receipt["loop_state"]["latest_decision_id"] == decision.decision_id
    assert status_receipt["loop_state"]["primary_failure_surface"] == "feature_materialization_gap"


def test_paper_practice_loop_requires_completed_historical_ladder(settings) -> None:
    run_migrations_to_head(settings)
    _seed_strategy_report(settings)

    runtime = PaperPracticeRuntime(settings)

    with pytest.raises(RuntimeError, match="run-paper-practice-bootstrap"):
        runtime.run_loop(max_iterations=1)


def test_ensure_advisory_strategy_report_runs_governed_strategy_eval_when_missing(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    _seed_research_repo_truth(settings.repo_root)
    report_path = (
        settings.repo_root
        / ".ai"
        / "dropbox"
        / "research"
        / "STRAT-001__strategy_challenger_report.json"
    )
    if report_path.exists():
        report_path.unlink()

    observed: dict[str, object] = {}

    class FakeShadowRunner:
        def __init__(self, runner_settings):
            observed["settings"] = runner_settings

        def run_strategy_eval_v1(self):
            observed["ran_strategy_eval"] = True
            _seed_strategy_report(settings)
            return {
                "run_id": "strategy_eval_generated",
                "artifact_dir": str(settings.data_dir / "research" / "strategy_eval_runs" / "generated"),
                "top_family": "trend_continuation_long_v1",
                "proposal_status": "proposed",
            }

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.shadow_runner.ShadowRunner",
        FakeShadowRunner,
    )

    result = PaperPracticeRuntime(settings)._ensure_advisory_strategy_report()

    assert result["status"] == "generated"
    assert result["run_id"] == "strategy_eval_generated"
    assert result["top_family"] == "trend_continuation_long_v1"
    assert result["strategy_report_exists"] is True
    assert observed["ran_strategy_eval"] is True


def test_lookup_backtest_price_uses_nearest_prior_or_next_price(settings) -> None:
    runtime = PaperPracticeRuntime(settings)
    price_history = pd.DataFrame(
        [
            {"start_time_utc": pd.Timestamp("2026-01-01T00:00:00Z"), "close": 100.0},
            {"start_time_utc": pd.Timestamp("2026-01-01T00:01:00Z"), "close": 101.0},
            {"start_time_utc": pd.Timestamp("2026-01-01T00:02:00Z"), "close": 102.0},
        ]
    )

    assert runtime._lookup_backtest_price(
        price_history,
        pd.Timestamp("2026-01-01T00:01:30Z"),
    ) == 101.0
    assert runtime._lookup_backtest_price(
        price_history,
        pd.Timestamp("2025-12-31T23:59:00Z"),
    ) == 100.0


def test_paper_practice_status_exposes_training_profile_readiness(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    settings.paper_practice_training_profile = "auto"
    runtime = PaperPracticeRuntime(settings)

    monkeypatch.setattr(
        PaperPracticeRuntime,
        "historical_cache_status",
        lambda self: {
            "complete": False,
            "completed_day_count": 0,
            "capture_completed_day_count": 335,
            "missing_day_count": 730,
            "next_missing_date": "2025-03-20",
        },
    )

    status = runtime.get_status()

    assert status["selected_training_profile"]["name"] == "quickstart_300d"
    assert status["selected_training_regimen"]["name"] == "quickstart_300d"
    assert status["selected_training_profile"]["ready"] is True
    assert status["training_profile_readiness"]["profiles"]["quickstart_300d"]["ready"] is True
    assert status["training_regimen_readiness"]["profiles"]["quickstart_300d"]["ready"] is True


def test_bootstrap_hydrates_selected_quickstart_regimen_window(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    settings.paper_practice_training_profile = "quickstart_300d"

    def _cache_status(self):
        return {
            "complete": False,
            "completed_day_count": 2,
            "capture_completed_day_count": 340,
            "missing_day_count": 728,
            "capture_missing_day_count": 390,
            "next_missing_date": "2025-06-01",
            "warehouse_completed_day_count": 2,
        }

    async def _forbid_full_tier_backfill(self, **kwargs):
        raise AssertionError("bootstrap must not call the full free-tier missing backfill")

    observed: dict[str, str] = {}

    async def _fake_backfill_range(self, *, start_date: str, end_date: str, resume: bool = True, mode: str = "range"):
        observed.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "resume": str(resume),
                "mode": mode,
            }
        )
        return {
            "status": "success",
            "batch_id": "capture_batch_quickstart",
            "mode": mode,
            "resume": resume,
            "resolved_start_date": start_date,
            "resolved_end_date": end_date,
            "days": {"requested_count": 300, "captured_count": 298, "skipped_count": 2, "failed_count": 0},
        }

    monkeypatch.setattr(PaperPracticeRuntime, "historical_cache_status", _cache_status)
    monkeypatch.setattr(MassiveMinuteAggsBackfill, "backfill_missing_full_free_tier", _forbid_full_tier_backfill)
    monkeypatch.setattr(MassiveMinuteAggsBackfill, "backfill_range", _fake_backfill_range)
    monkeypatch.setattr(
        "d5_trading_engine.features.materializer.FeatureMaterializer.materialize_global_regime_inputs_15m_v1",
        lambda self: ("feature_quickstart", 1234),
    )
    monkeypatch.setattr(
        "d5_trading_engine.research_loop.regime_model_compare.RegimeModelComparator.run_regime_model_compare_v1",
        lambda self, **kwargs: {
            "run_id": "comparison_quickstart",
            "recommended_candidate": "baseline",
            "proposal_status": "shadow",
        },
    )
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "run_backtest_walk_forward",
        lambda self, training_profile_name=None: {
            "run_id": "backtest_quickstart",
            "window_count": 1,
            "completed_ladder": True,
            "history_window": {"ready": True},
            "active_revision_id": "paper_profile_revision_test",
        },
    )

    runtime = PaperPracticeRuntime(settings)
    result = runtime.run_bootstrap()

    assert result["training_profile"]["name"] == "quickstart_300d"
    assert observed["mode"] == "quickstart_300d"
    assert observed["resume"] == "True"
