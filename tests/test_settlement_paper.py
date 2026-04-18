from __future__ import annotations

import json
from datetime import timedelta

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.execution_intent.owner import ExecutionIntentOwner
from d5_trading_engine.policy.global_regime_v1 import GlobalRegimePolicyEvaluator
from d5_trading_engine.risk.gate import RiskGate
from d5_trading_engine.settlement.paper import PaperSettlement
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    ExecutionIntentV1,
    FeatureMaterializationRun,
    IngestRun,
    PaperFill,
    PaperPosition,
    PaperSession,
    PaperSessionReport,
    QuoteSnapshot,
    TokenRegistry,
)


def _freshness_snapshot() -> dict[str, object]:
    return {
        "generated_at_utc": utcnow().isoformat(),
        "required_lanes": {
            "coinbase-candles": {
                "required_for_authorization": True,
                "downstream_eligible": True,
                "freshness_state": "healthy_recent",
                "latest_error_summary": None,
            },
            "coinbase-market-trades": {
                "required_for_authorization": True,
                "downstream_eligible": True,
                "freshness_state": "healthy_recent",
                "latest_error_summary": None,
            },
            "coinbase-book": {
                "required_for_authorization": True,
                "downstream_eligible": True,
                "freshness_state": "healthy_recent",
                "latest_error_summary": None,
            },
        },
        "authorized": True,
        "blocking_lanes": [],
    }


def _seed_policy_trace(
    settings,
    *,
    run_id: str,
    semantic_regime: str,
) -> int:
    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    started_at = now - timedelta(minutes=10)
    finished_at = started_at + timedelta(minutes=1)
    feature_run_id = f"feature_{run_id}"
    try:
        session.add(
            FeatureMaterializationRun(
                run_id=feature_run_id,
                feature_set="global_regime_inputs_15m_v1",
                source_tables="[]",
                freshness_snapshot_json=json.dumps(_freshness_snapshot()),
                status="success",
                started_at=started_at - timedelta(minutes=30),
                finished_at=started_at - timedelta(minutes=29),
                created_at=started_at - timedelta(minutes=30),
            )
        )
        session.flush()
        session.add(
            ConditionScoringRun(
                run_id=run_id,
                condition_set="global_regime_v1",
                source_feature_run_id=feature_run_id,
                model_family="gaussian_hmm_4state",
                status="success",
                confidence=0.81,
                started_at=started_at,
                finished_at=finished_at,
                created_at=started_at,
            )
        )
        session.flush()
        session.add(
            ConditionGlobalRegimeSnapshotV1(
                condition_run_id=run_id,
                source_feature_run_id=feature_run_id,
                bucket_start_utc=started_at - timedelta(minutes=15),
                raw_state_id=1,
                semantic_regime=semantic_regime,
                confidence=0.81,
                blocked_flag=0,
                blocking_reason=None,
                model_family="gaussian_hmm_4state",
                macro_context_state="degraded",
                created_at=finished_at,
            )
        )
        session.commit()
    finally:
        session.close()
    return GlobalRegimePolicyEvaluator(settings).evaluate(condition_run_id=run_id)["trace_id"]


def _seed_quote_snapshot(
    settings,
    *,
    run_id: str,
    request_direction: str,
    input_mint: str,
    output_mint: str,
    input_amount: str,
    output_amount: str,
    captured_at=None,
) -> int:
    session = get_session(settings)
    now = captured_at or utcnow().replace(second=0, microsecond=0)
    try:
        session.add(
            IngestRun(
                run_id=run_id,
                provider="jupiter",
                capture_type="quotes",
                status="success",
                started_at=now - timedelta(seconds=2),
                finished_at=now - timedelta(seconds=1),
                records_captured=1,
                error_message=None,
                created_at=now - timedelta(seconds=2),
            )
        )
        for mint, symbol, name, decimals in (
            (
                input_mint,
                "USDC" if input_mint.endswith("TDt1v") else "SOL",
                "Input token",
                6 if input_mint.endswith("TDt1v") else 9,
            ),
            (
                output_mint,
                "USDC" if output_mint.endswith("TDt1v") else "SOL",
                "Output token",
                6 if output_mint.endswith("TDt1v") else 9,
            ),
        ):
            existing = session.query(TokenRegistry).filter_by(mint=mint).first()
            if existing is None:
                session.add(
                    TokenRegistry(
                        mint=mint,
                        symbol=symbol,
                        name=name,
                        decimals=decimals,
                        logo_uri=None,
                        tags=None,
                        provider="jupiter",
                        first_seen_at=now,
                        updated_at=now,
                    )
                )
        session.flush()
        row = QuoteSnapshot(
            ingest_run_id=run_id,
            input_mint=input_mint,
            output_mint=output_mint,
            input_amount=input_amount,
            output_amount=output_amount,
            price_impact_pct=0.12,
            slippage_bps=50,
            route_plan_json="[]",
            other_amount_threshold="0",
            swap_mode="ExactIn",
            request_direction=request_direction,
            requested_at=now,
            response_latency_ms=150.0,
            source_event_time_utc=now,
            source_time_raw=now.isoformat(),
            event_date_utc=now.strftime("%Y-%m-%d"),
            hour_utc=now.hour,
            minute_of_day_utc=(now.hour * 60) + now.minute,
            weekday_utc=now.weekday(),
            time_quality="source",
            provider="jupiter",
            captured_at=now,
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _seed_allowed_risk_verdict(settings, *, run_id: str, semantic_regime: str) -> int:
    trace_id = _seed_policy_trace(settings, run_id=run_id, semantic_regime=semantic_regime)
    return RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)["risk_verdict_id"]


def _seed_execution_intent(
    settings,
    *,
    risk_verdict_id: int,
    quote_snapshot_id: int,
    intent_created_at=None,
) -> dict[str, object]:
    return ExecutionIntentOwner(settings).create_spot_intent(
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
        intent_created_at=intent_created_at,
    )


def _tracked_mint(settings, symbol: str) -> str:
    return next(
        mint
        for mint, minted_symbol in settings.token_symbol_hints.items()
        if minted_symbol == symbol
    )


def test_paper_settlement_creates_quote_backed_fill_and_report(settings) -> None:
    run_migrations_to_head(settings)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="settlement_long_allowed",
        semantic_regime="long_friendly",
    )
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_long_allowed",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )
    execution_intent = _seed_execution_intent(
        settings,
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
    )

    result = PaperSettlement(settings).simulate_fill(
        execution_intent_id=execution_intent["execution_intent_id"],
    )

    assert result["filled"] is True
    assert result["session_status"] == "open"
    assert result["reason_codes"] == []
    assert result["is_scaffold"] is False

    portfolio = PaperSettlement(settings).get_portfolio_state(result["session_key"])
    assert portfolio["session_found"] is True
    assert portfolio["cash_usdc"] == 0.0
    assert portfolio["position_value_usdc"] == 10.0
    assert portfolio["total_value_usdc"] == 10.0
    assert portfolio["positions"][0]["mint"] == sol_mint
    assert portfolio["positions"][0]["net_quantity"] == 0.1

    session = get_session(settings)
    try:
        execution_intent_row = session.query(ExecutionIntentV1).one()
        paper_session = session.query(PaperSession).one()
        paper_fill = session.query(PaperFill).one()
        paper_position = session.query(PaperPosition).one()
        paper_report = session.query(PaperSessionReport).one()
    finally:
        session.close()

    assert execution_intent_row.intent_state == "ready"
    assert paper_session.status == "open"
    assert paper_session.base_currency == "USDC"
    assert paper_session.quote_size_lamports == 10_000_000
    assert paper_fill.execution_intent_id == execution_intent["execution_intent_id"]
    assert paper_fill.risk_verdict_id == risk_verdict_id
    assert paper_fill.quote_snapshot_id == quote_snapshot_id
    assert paper_fill.fill_side == "buy"
    assert paper_fill.fill_role == "entry"
    assert paper_fill.fill_price_usdc == 100.0
    assert paper_position.cost_basis_usdc == 10.0
    assert paper_position.last_mark_source == "fill_quote"
    assert paper_report.report_type == "session_snapshot"
    assert paper_report.mark_method == "fill_quote"
    assert paper_report.equity_usdc == 10.0


def test_paper_settlement_can_close_an_open_session_from_exit_quote(settings) -> None:
    run_migrations_to_head(settings)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="settlement_close_allowed",
        semantic_regime="long_friendly",
    )
    entry_quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_close_entry",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )
    execution_intent = _seed_execution_intent(
        settings,
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=entry_quote_snapshot_id,
    )
    opened = PaperSettlement(settings).simulate_fill(
        execution_intent_id=execution_intent["execution_intent_id"],
    )

    close_quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_close_exit",
        request_direction="token_to_usdc",
        input_mint=sol_mint,
        output_mint=usdc_mint,
        input_amount="100000000",
        output_amount="10500000",
    )
    policy_trace_id = _seed_policy_trace(
        settings,
        run_id="condition_close_allowed",
        semantic_regime="long_friendly",
    )

    session = get_session(settings)
    try:
        latest_fill = session.query(PaperFill).order_by(PaperFill.id.desc()).first()
    finally:
        session.close()
    assert latest_fill is not None

    result = PaperSettlement(settings).simulate_close(
        session_key=str(opened["session_key"]),
        quote_snapshot_id=close_quote_snapshot_id,
        policy_trace_id=policy_trace_id,
        risk_verdict_id=risk_verdict_id,
        condition_snapshot_id=int(latest_fill.condition_snapshot_id),
        source_feature_run_id=str(latest_fill.source_feature_run_id),
        policy_state="eligible_long",
        risk_state="allowed",
        close_reason="take_profit",
    )

    assert result["closed"] is True
    assert result["session_status"] == "closed"
    assert result["realized_pnl_usdc"] == 0.5
    assert result["reason_codes"] == ["close_reason:take_profit"]

    portfolio = PaperSettlement(settings).get_portfolio_state(str(opened["session_key"]))
    assert portfolio["session_status"] == "closed"
    assert portfolio["cash_usdc"] == 10.5
    assert portfolio["position_value_usdc"] == 0.0
    assert portfolio["total_value_usdc"] == 10.5

    session = get_session(settings)
    try:
        paper_session = session.query(PaperSession).one()
        fills = session.query(PaperFill).order_by(PaperFill.id.asc()).all()
        paper_position = session.query(PaperPosition).one()
        reports = session.query(PaperSessionReport).order_by(PaperSessionReport.id.asc()).all()
    finally:
        session.close()

    assert paper_session.status == "closed"
    assert len(fills) == 2
    assert fills[-1].fill_role == "exit"
    assert paper_position.net_quantity == 0.0
    assert paper_position.realized_pnl_usdc == 0.5
    assert reports[-1].report_type == "session_close"
    assert reports[-1].realized_pnl_usdc == 0.5


def test_paper_settlement_skips_non_allowed_risk_verdict(settings) -> None:
    run_migrations_to_head(settings)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="settlement_short_allowed",
        semantic_regime="short_friendly",
    )
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_short_allowed",
        request_direction="token_to_usdc",
        input_mint=sol_mint,
        output_mint=usdc_mint,
        input_amount="100000000",
        output_amount="10000000",
    )
    execution_intent = _seed_execution_intent(
        settings,
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
    )

    result = PaperSettlement(settings).simulate_fill(
        execution_intent_id=execution_intent["execution_intent_id"],
    )

    assert result["filled"] is False
    assert result["session_status"] == "skipped"
    assert "execution_intent_not_ready:rejected" in result["reason_codes"]
    assert "policy_state_unsupported_for_spot_intent:eligible_short" in result["reason_codes"]
    assert "quote_direction_incompatible:token_to_usdc" in result["reason_codes"]

    session = get_session(settings)
    try:
        intent_row = session.query(ExecutionIntentV1).one()
        assert session.query(PaperSession).count() == 1
        assert session.query(PaperFill).count() == 0
        assert session.query(PaperPosition).count() == 0
        report = session.query(PaperSessionReport).one()
    finally:
        session.close()

    assert intent_row.intent_state == "rejected"
    assert report.report_type == "session_close"
    assert report.position_value_usdc == 0.0


def test_paper_settlement_skips_stale_quote_without_fill(settings) -> None:
    run_migrations_to_head(settings)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="settlement_stale_quote",
        semantic_regime="long_friendly",
    )
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_stale",
        request_direction="buy",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
        captured_at=utcnow() - timedelta(minutes=15),
    )
    execution_intent = _seed_execution_intent(
        settings,
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
    )

    result = PaperSettlement(settings).simulate_fill(
        execution_intent_id=execution_intent["execution_intent_id"],
    )

    assert result["filled"] is False
    assert result["session_status"] == "skipped"
    assert "execution_intent_not_ready:rejected" in result["reason_codes"]
    assert "execution_intent_quote_stale" in result["reason_codes"]

    session = get_session(settings)
    try:
        assert session.query(PaperFill).count() == 0
        assert session.query(PaperPosition).count() == 0
        assert session.query(PaperSessionReport).count() == 1
    finally:
        session.close()


def test_paper_settlement_skips_missing_quote_snapshot(settings) -> None:
    run_migrations_to_head(settings)
    risk_verdict_id = _seed_allowed_risk_verdict(
        settings,
        run_id="settlement_missing_quote",
        semantic_regime="long_friendly",
    )
    execution_intent = _seed_execution_intent(
        settings,
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=99999,
    )

    result = PaperSettlement(settings).simulate_fill(
        execution_intent_id=execution_intent["execution_intent_id"],
    )

    assert result["filled"] is False
    assert result["session_status"] == "skipped"
    assert "execution_intent_not_ready:rejected" in result["reason_codes"]
    assert "quote_snapshot_missing" in result["reason_codes"]

    session = get_session(settings)
    try:
        assert session.query(PaperSession).count() == 1
        assert session.query(PaperFill).count() == 0
        report = session.query(PaperSessionReport).one()
    finally:
        session.close()

    assert report.cash_usdc == 0.0
