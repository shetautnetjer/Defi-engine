from __future__ import annotations

from datetime import timedelta

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.execution_intent.owner import ExecutionIntentOwner
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import ExecutionIntentV1
from tests.test_settlement_paper import (
    _seed_allowed_risk_verdict,
    _seed_quote_snapshot,
    _tracked_mint,
)


def test_execution_intent_owner_persists_ready_spot_intent(settings) -> None:
    run_migrations_to_head(settings)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="exec_owner_ready",
        semantic_regime="long_friendly",
    )
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="exec_owner_quote_ready",
        request_direction="buy",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )

    result = ExecutionIntentOwner(settings).create_spot_intent(
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
    )

    assert result["ready"] is True
    assert result["intent_state"] == "ready"
    assert result["intent_side"] == "buy"
    assert result["settlement_model"] == "paper_spot_v1"
    assert result["reason_codes"] == []

    session = get_session(settings)
    try:
        row = session.query(ExecutionIntentV1).one()
    finally:
        session.close()

    assert row.risk_verdict_id == risk_verdict_id
    assert row.quote_snapshot_id == quote_snapshot_id
    assert row.request_direction == "usdc_to_token"
    assert row.input_mint == usdc_mint
    assert row.output_mint == sol_mint
    assert row.quote_size_lamports == 10_000_000
    assert row.intent_state == "ready"


def test_execution_intent_owner_rejects_stale_quote(settings) -> None:
    run_migrations_to_head(settings)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="exec_owner_stale",
        semantic_regime="long_friendly",
    )
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="exec_owner_quote_stale",
        request_direction="buy",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
        captured_at=utcnow() - timedelta(minutes=10),
    )

    result = ExecutionIntentOwner(settings).create_spot_intent(
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
    )

    assert result["ready"] is False
    assert result["intent_state"] == "rejected"
    assert "execution_intent_quote_stale" in result["reason_codes"]
