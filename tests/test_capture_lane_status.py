from __future__ import annotations

from d5_trading_engine.capture.lane_status import (
    build_capture_lane_status_snapshot,
    build_feature_lane_snapshot,
)
from d5_trading_engine.cli import cli
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import IngestRun, RawHeliusWsEvent, SourceHealthEvent


def _seed_ingest_run(session, *, run_id: str, provider: str, capture_type: str, at) -> None:
    session.add(
        IngestRun(
            run_id=run_id,
            provider=provider,
            capture_type=capture_type,
            status="success",
            started_at=at,
            finished_at=at,
            records_captured=1,
            created_at=at,
        )
    )


def _seed_health_event(session, *, provider: str, endpoint: str, at) -> None:
    session.add(
        SourceHealthEvent(
            provider=provider,
            endpoint=endpoint,
            status_code=200,
            latency_ms=50.0,
            is_healthy=1,
            error_message=None,
            checked_at=at,
        )
    )


def test_feature_lane_snapshot_uses_lane_specific_health_receipts(
    cli_runner, settings
) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0

    now = utcnow().replace(second=0, microsecond=0)
    session = get_session(settings)
    try:
        _seed_ingest_run(
            session,
            run_id="jupiter_prices_run_001",
            provider="jupiter",
            capture_type="prices",
            at=now,
        )
        _seed_ingest_run(
            session,
            run_id="jupiter_quotes_run_001",
            provider="jupiter",
            capture_type="quotes",
            at=now,
        )
        _seed_health_event(session, provider="jupiter", endpoint="/price/v3", at=now)
        session.commit()
    finally:
        session.close()

    snapshot = build_feature_lane_snapshot(
        required_lanes=("jupiter-prices", "jupiter-quotes"),
        settings=settings,
    )

    assert (
        snapshot["required_lanes"]["jupiter-prices"]["freshness_state"] == "healthy_recent"
    )
    assert snapshot["required_lanes"]["jupiter-quotes"]["freshness_state"] == "degraded"
    assert snapshot["blocking_lanes"] == ["jupiter-quotes=degraded"]


def test_capture_lane_status_snapshot_reports_ws_receipts_and_readiness_only(
    cli_runner, settings
) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0

    now = utcnow().replace(second=0, microsecond=0)
    session = get_session(settings)
    try:
        _seed_ingest_run(
            session,
            run_id="helius_ws_run_001",
            provider="helius",
            capture_type="ws_events",
            at=now,
        )
        _seed_health_event(
            session,
            provider="helius",
            endpoint="transactionSubscribe",
            at=now,
        )
        session.add(
            RawHeliusWsEvent(
                ingest_run_id="helius_ws_run_001",
                provider="helius",
                subscription_id="sub-1",
                event_type="notification",
                payload="{}",
                captured_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    snapshot = build_capture_lane_status_snapshot(settings=settings)

    ws_lane = snapshot["lanes"]["helius-ws-events"]
    assert ws_lane["freshness_state"] == "healthy_recent"
    assert ws_lane["latest_raw_receipt_at_utc"] is not None

    massive_lane = snapshot["lanes"]["massive-crypto"]
    assert massive_lane["freshness_state"] == "readiness_only"
    assert massive_lane["downstream_eligible"] is False
