from __future__ import annotations

import json

import pytest

from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
    PaperPracticeProfileRevisionV1,
    PaperPracticeProfileV1,
)
from tests.test_backtest_walk_forward import _seed_strategy_report
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


def test_paper_practice_loop_requires_completed_historical_ladder(settings) -> None:
    run_migrations_to_head(settings)
    _seed_strategy_report(settings)

    runtime = PaperPracticeRuntime(settings)

    with pytest.raises(RuntimeError, match="run-paper-practice-bootstrap"):
        runtime.run_loop(max_iterations=1)


def test_paper_practice_status_exposes_training_profile_readiness(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    runtime = PaperPracticeRuntime(settings)

    monkeypatch.setattr(
        PaperPracticeRuntime,
        "historical_cache_status",
        lambda self: {
            "complete": False,
            "completed_day_count": 335,
            "missing_day_count": 395,
            "next_missing_date": "2025-03-20",
        },
    )

    status = runtime.get_status()

    assert status["selected_training_profile"]["name"] == "full_730d"
    assert status["selected_training_regimen"]["name"] == "full_730d"
    assert status["selected_training_profile"]["ready"] is False
    assert status["training_profile_readiness"]["profiles"]["quickstart_300d"]["ready"] is True
    assert status["training_regimen_readiness"]["profiles"]["quickstart_300d"]["ready"] is True
