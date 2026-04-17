from __future__ import annotations

from datetime import timedelta

import pytest

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.settlement.backtest import BacktestTruthOwner
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    BacktestFillV1,
    BacktestPositionV1,
    BacktestSessionReportV1,
    BacktestSessionV1,
    TokenRegistry,
)


def _tracked_mint(settings, symbol: str) -> str:
    return next(
        mint
        for mint, minted_symbol in settings.token_symbol_hints.items()
        if minted_symbol == symbol
    )


def _seed_tracked_tokens(settings) -> tuple[str, str]:
    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    try:
        for mint, symbol, decimals in (
            (usdc_mint, "USDC", 6),
            (sol_mint, "SOL", 9),
        ):
            if session.query(TokenRegistry).filter_by(mint=mint).first() is None:
                session.add(
                    TokenRegistry(
                        mint=mint,
                        symbol=symbol,
                        name=symbol,
                        decimals=decimals,
                        logo_uri=None,
                        tags=None,
                        provider="test",
                        first_seen_at=now,
                        updated_at=now,
                    )
                )
        session.commit()
    finally:
        session.close()
    return usdc_mint, sol_mint


def test_backtest_truth_owner_opens_replays_and_closes_spot_session(settings) -> None:
    run_migrations_to_head(settings)
    _, sol_mint = _seed_tracked_tokens(settings)
    owner = BacktestTruthOwner(settings)
    started_at = utcnow().replace(second=0, microsecond=0)

    opened = owner.open_spot_session(
        session_key="backtest_exec_001",
        bucket_granularity="15m",
        fee_bps=10,
        slippage_bps=25,
        latency_ms=150,
        starting_cash_usdc=100.0,
        metadata={"story_id": "BACKTEST-001"},
        opened_at=started_at,
    )

    assert opened["session_status"] == "open"
    assert opened["instrument_family"] == "spot"
    assert opened["venue"] == "jupiter_spot"

    buy = owner.record_fill(
        session_id=opened["session_id"],
        event_time=started_at + timedelta(minutes=15),
        mint=sol_mint,
        side="buy",
        input_amount="10000000",
        output_amount="100000000",
        fill_price_usdc=100.0,
        replay_reference="bucket:2026-04-17T00:15:00Z",
    )
    assert buy["cash_usdc"] == pytest.approx(89.99)
    assert buy["position_value_usdc"] == pytest.approx(10.0)
    assert buy["equity_usdc"] == pytest.approx(99.99)

    sell = owner.record_fill(
        session_id=opened["session_id"],
        event_time=started_at + timedelta(minutes=30),
        mint=sol_mint,
        side="sell",
        input_amount="50000000",
        output_amount="6000000",
        fill_price_usdc=120.0,
        replay_reference="bucket:2026-04-17T00:30:00Z",
    )
    assert sell["cash_usdc"] == pytest.approx(95.984)
    assert sell["position_value_usdc"] == pytest.approx(6.0)
    assert sell["realized_pnl_usdc"] == pytest.approx(0.989)

    closed = owner.close_session(
        session_id=opened["session_id"],
        closed_at=started_at + timedelta(minutes=45),
        mark_prices_usdc={sol_mint: 110.0},
        mark_reference="mark:2026-04-17T00:45:00Z",
    )
    assert closed["session_status"] == "closed"
    assert closed["cash_usdc"] == pytest.approx(95.984)
    assert closed["position_value_usdc"] == pytest.approx(5.5)
    assert closed["realized_pnl_usdc"] == pytest.approx(0.989)
    assert closed["unrealized_pnl_usdc"] == pytest.approx(0.495)
    assert closed["equity_usdc"] == pytest.approx(101.484)

    session = get_session(settings)
    try:
        backtest_session = session.query(BacktestSessionV1).one()
        fills = session.query(BacktestFillV1).order_by(BacktestFillV1.id.asc()).all()
        position = session.query(BacktestPositionV1).one()
        report = (
            session.query(BacktestSessionReportV1)
            .filter_by(session_id=backtest_session.id, report_type="session_close")
            .one()
        )
    finally:
        session.close()

    assert backtest_session.bucket_granularity == "15m"
    assert backtest_session.fee_bps == 10
    assert backtest_session.slippage_bps == 25
    assert backtest_session.latency_ms == 150
    assert backtest_session.status == "closed"
    assert len(fills) == 2
    assert fills[0].fee_usdc == pytest.approx(0.01)
    assert fills[1].fee_usdc == pytest.approx(0.006)
    assert position.net_quantity == pytest.approx(0.05)
    assert position.cost_basis_usdc == pytest.approx(5.005)
    assert position.realized_pnl_usdc == pytest.approx(0.989)
    assert position.unrealized_pnl_usdc == pytest.approx(0.495)
    assert report.mark_method == "replay_last_fill"


def test_backtest_truth_owner_rejects_unsupported_instrument_family(settings) -> None:
    run_migrations_to_head(settings)
    owner = BacktestTruthOwner(settings)

    with pytest.raises(ValueError, match="backtest_instrument_family_unsupported:perp"):
        owner.open_spot_session(
            session_key="backtest_invalid_instrument",
            instrument_family="perp",
            bucket_granularity="15m",
            fee_bps=10,
            slippage_bps=25,
            latency_ms=150,
        )


def test_backtest_truth_owner_rejects_non_monotonic_fill_timestamps(settings) -> None:
    run_migrations_to_head(settings)
    _, sol_mint = _seed_tracked_tokens(settings)
    owner = BacktestTruthOwner(settings)
    started_at = utcnow().replace(second=0, microsecond=0)
    opened = owner.open_spot_session(
        session_key="backtest_non_monotonic",
        bucket_granularity="15m",
        fee_bps=10,
        slippage_bps=25,
        latency_ms=150,
        starting_cash_usdc=100.0,
        opened_at=started_at,
    )
    owner.record_fill(
        session_id=opened["session_id"],
        event_time=started_at + timedelta(minutes=15),
        mint=sol_mint,
        side="buy",
        input_amount="10000000",
        output_amount="100000000",
        fill_price_usdc=100.0,
        replay_reference="bucket:1",
    )

    with pytest.raises(ValueError, match="backtest_fill_event_time_non_monotonic"):
        owner.record_fill(
            session_id=opened["session_id"],
            event_time=started_at + timedelta(minutes=15),
            mint=sol_mint,
            side="buy",
            input_amount="1000000",
            output_amount="10000000",
            fill_price_usdc=100.0,
            replay_reference="bucket:1-repeat",
        )


def test_backtest_truth_owner_requires_marks_for_open_positions(settings) -> None:
    run_migrations_to_head(settings)
    _, sol_mint = _seed_tracked_tokens(settings)
    owner = BacktestTruthOwner(settings)
    started_at = utcnow().replace(second=0, microsecond=0)
    opened = owner.open_spot_session(
        session_key="backtest_missing_mark",
        bucket_granularity="15m",
        fee_bps=10,
        slippage_bps=25,
        latency_ms=150,
        starting_cash_usdc=100.0,
        opened_at=started_at,
    )
    owner.record_fill(
        session_id=opened["session_id"],
        event_time=started_at + timedelta(minutes=15),
        mint=sol_mint,
        side="buy",
        input_amount="10000000",
        output_amount="100000000",
        fill_price_usdc=100.0,
        replay_reference="bucket:missing-mark",
    )

    with pytest.raises(ValueError, match="backtest_close_mark_reference_missing"):
        owner.close_session(
            session_id=opened["session_id"],
            closed_at=started_at + timedelta(minutes=30),
            mark_prices_usdc={sol_mint: 110.0},
        )
