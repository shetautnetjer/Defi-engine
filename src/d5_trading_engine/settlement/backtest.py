"""Settlement-owned backtest replay ledger for spot-first truth."""

from __future__ import annotations

import re
from datetime import datetime

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    BacktestFillV1,
    BacktestPositionV1,
    BacktestSessionReportV1,
    BacktestSessionV1,
    TokenMetadataSnapshot,
    TokenRegistry,
)

log = get_logger(__name__)

_USDC_DECIMALS = 6
_GRANULARITY_PATTERN = re.compile(r"^\d+(m|h|d)$")


class BacktestTruthOwner:
    """Spot-only backtest replay owner with explicit assumptions."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def open_spot_session(
        self,
        *,
        session_key: str,
        bucket_granularity: str,
        fee_bps: int,
        slippage_bps: int,
        latency_ms: int,
        starting_cash_usdc: float = 0.0,
        instrument_family: str = "spot",
        venue: str = "jupiter_spot",
        base_currency: str = "USDC",
        mark_method: str = "replay_last_fill",
        metadata: dict[str, object] | None = None,
        opened_at: datetime | None = None,
    ) -> dict[str, object]:
        opened_at_utc = ensure_utc(opened_at) or utcnow()
        self._validate_open_inputs(
            session_key=session_key,
            instrument_family=instrument_family,
            venue=venue,
            base_currency=base_currency,
            bucket_granularity=bucket_granularity,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            latency_ms=latency_ms,
            starting_cash_usdc=starting_cash_usdc,
            mark_method=mark_method,
        )

        session = get_session(self.settings)
        try:
            existing = session.query(BacktestSessionV1).filter_by(session_key=session_key).first()
            if existing is not None:
                raise ValueError(f"backtest_session_key_exists:{session_key}")

            row = BacktestSessionV1(
                session_key=session_key,
                status="open",
                instrument_family=instrument_family,
                venue=venue,
                base_currency=base_currency,
                bucket_granularity=bucket_granularity,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps,
                latency_ms=latency_ms,
                mark_method=mark_method,
                metadata_json=self._encode_json(metadata or {}),
                starting_cash_usdc=float(starting_cash_usdc),
                ending_cash_usdc=None,
                opened_at=opened_at_utc,
                closed_at=None,
                reason_codes_json=self._encode_json([]),
                created_at=opened_at_utc,
            )
            session.add(row)
            session.commit()
            log.info("backtest_session_opened", session_id=row.id, session_key=row.session_key)
            return {
                "session_id": row.id,
                "session_key": row.session_key,
                "session_status": row.status,
                "instrument_family": row.instrument_family,
                "venue": row.venue,
                "base_currency": row.base_currency,
                "bucket_granularity": row.bucket_granularity,
                "fee_bps": row.fee_bps,
                "slippage_bps": row.slippage_bps,
                "latency_ms": row.latency_ms,
                "starting_cash_usdc": row.starting_cash_usdc,
                "mark_method": row.mark_method,
                "is_scaffold": False,
            }
        finally:
            session.close()

    def record_fill(
        self,
        *,
        session_id: int,
        event_time: datetime,
        mint: str,
        side: str,
        input_amount: str,
        output_amount: str,
        fill_price_usdc: float,
        replay_reference: str,
        reason_codes: list[str] | None = None,
    ) -> dict[str, object]:
        event_time_utc = ensure_utc(event_time)
        if event_time_utc is None:
            raise ValueError("backtest_fill_event_time_missing")
        if not replay_reference:
            raise ValueError("backtest_fill_replay_reference_missing")

        normalized_side = self._normalize_side(side)
        if normalized_side is None:
            raise ValueError(f"backtest_fill_side_unsupported:{side}")
        if fill_price_usdc <= 0:
            raise ValueError("backtest_fill_price_invalid")

        session = get_session(self.settings)
        try:
            backtest_session = (
                session.query(BacktestSessionV1).filter_by(id=session_id).first()
            )
            if backtest_session is None:
                raise ValueError(f"backtest_session_missing:{session_id}")
            if backtest_session.status != "open":
                raise ValueError(f"backtest_session_not_open:{backtest_session.status}")

            last_fill = (
                session.query(BacktestFillV1)
                .filter_by(session_id=session_id)
                .order_by(BacktestFillV1.event_time.desc(), BacktestFillV1.id.desc())
                .first()
            )
            if last_fill is not None and event_time_utc <= ensure_utc(last_fill.event_time):
                raise ValueError("backtest_fill_event_time_non_monotonic")

            mint_decimals = self._resolve_token_decimals(session=session, mint=mint)
            if mint_decimals is None or mint == self._usdc_mint():
                raise ValueError(f"backtest_fill_mint_unsupported:{mint}")

            input_amount_int = self._parse_int(input_amount)
            output_amount_int = self._parse_int(output_amount)
            if input_amount_int is None or input_amount_int <= 0:
                raise ValueError("backtest_fill_input_amount_invalid")
            if output_amount_int is None or output_amount_int <= 0:
                raise ValueError("backtest_fill_output_amount_invalid")

            position = (
                session.query(BacktestPositionV1)
                .filter_by(session_id=session_id, mint=mint)
                .first()
            )
            previous_cash = self._current_cash(session=session, session_id=session_id, fallback=backtest_session.starting_cash_usdc)
            fee_usdc = self._compute_fee_usdc(
                side=normalized_side,
                input_amount_int=input_amount_int,
                output_amount_int=output_amount_int,
                fee_bps=backtest_session.fee_bps,
                mint_decimals=mint_decimals,
            )

            cash_after, net_quantity, cost_basis_usdc, realized_pnl_usdc = self._apply_fill(
                side=normalized_side,
                previous_cash=previous_cash,
                position=position,
                input_amount_int=input_amount_int,
                output_amount_int=output_amount_int,
                mint_decimals=mint_decimals,
                fee_usdc=fee_usdc,
            )

            fill_row = BacktestFillV1(
                session_id=session_id,
                event_time=event_time_utc,
                replay_reference=replay_reference,
                mint=mint,
                side=normalized_side,
                input_amount=str(input_amount_int),
                output_amount=str(output_amount_int),
                fill_price_usdc=float(fill_price_usdc),
                fee_bps=backtest_session.fee_bps,
                fee_usdc=fee_usdc,
                slippage_bps=backtest_session.slippage_bps,
                latency_ms=backtest_session.latency_ms,
                reason_codes_json=self._encode_json(reason_codes or []),
                created_at=event_time_utc,
            )
            session.add(fill_row)
            session.flush()

            if position is None:
                position = BacktestPositionV1(
                    session_id=session_id,
                    mint=mint,
                    net_quantity=net_quantity,
                    cost_basis_usdc=cost_basis_usdc,
                    last_fill_id=fill_row.id,
                    last_mark_source="fill_replay",
                    last_mark_reference=replay_reference,
                    last_mark_price_usdc=float(fill_price_usdc),
                    last_marked_at=event_time_utc,
                    realized_pnl_usdc=realized_pnl_usdc,
                    unrealized_pnl_usdc=0.0,
                    updated_at=event_time_utc,
                )
                session.add(position)
            else:
                position.net_quantity = net_quantity
                position.cost_basis_usdc = cost_basis_usdc
                position.last_fill_id = fill_row.id
                position.last_mark_source = "fill_replay"
                position.last_mark_reference = replay_reference
                position.last_mark_price_usdc = float(fill_price_usdc)
                position.last_marked_at = event_time_utc
                position.realized_pnl_usdc = realized_pnl_usdc
                position.unrealized_pnl_usdc = 0.0
                position.updated_at = event_time_utc

            report_row = BacktestSessionReportV1(
                session_id=session_id,
                report_type="session_snapshot",
                cash_usdc=cash_after,
                position_value_usdc=self._position_value_usdc(position),
                equity_usdc=cash_after + self._position_value_usdc(position),
                realized_pnl_usdc=position.realized_pnl_usdc,
                unrealized_pnl_usdc=0.0,
                mark_method="fill_replay",
                mark_inputs_json=self._encode_json(
                    {
                        "replay_reference": replay_reference,
                        "fill_id": fill_row.id,
                        "fill_price_usdc": float(fill_price_usdc),
                    }
                ),
                reason_codes_json=self._encode_json(reason_codes or []),
                created_at=event_time_utc,
            )
            session.add(report_row)
            session.commit()
            log.info("backtest_fill_recorded", session_id=session_id, fill_id=fill_row.id, mint=mint)
            return {
                "session_id": session_id,
                "fill_id": fill_row.id,
                "position_id": position.id,
                "report_id": report_row.id,
                "side": fill_row.side,
                "cash_usdc": report_row.cash_usdc,
                "position_value_usdc": report_row.position_value_usdc,
                "equity_usdc": report_row.equity_usdc,
                "realized_pnl_usdc": report_row.realized_pnl_usdc,
                "unrealized_pnl_usdc": report_row.unrealized_pnl_usdc,
                "reason_codes": reason_codes or [],
                "is_scaffold": False,
            }
        finally:
            session.close()

    def close_session(
        self,
        *,
        session_id: int,
        closed_at: datetime,
        mark_prices_usdc: dict[str, float] | None = None,
        mark_reference: str | None = None,
        mark_method: str | None = None,
        reason_codes: list[str] | None = None,
    ) -> dict[str, object]:
        closed_at_utc = ensure_utc(closed_at)
        if closed_at_utc is None:
            raise ValueError("backtest_close_time_missing")

        session = get_session(self.settings)
        try:
            backtest_session = (
                session.query(BacktestSessionV1).filter_by(id=session_id).first()
            )
            if backtest_session is None:
                raise ValueError(f"backtest_session_missing:{session_id}")
            if backtest_session.status != "open":
                raise ValueError(f"backtest_session_not_open:{backtest_session.status}")

            positions = (
                session.query(BacktestPositionV1)
                .filter_by(session_id=session_id)
                .order_by(BacktestPositionV1.mint.asc())
                .all()
            )
            open_positions = [row for row in positions if row.net_quantity > 0]
            mark_prices = mark_prices_usdc or {}
            if open_positions:
                if not mark_reference:
                    raise ValueError("backtest_close_mark_reference_missing")
                missing_marks = [row.mint for row in open_positions if row.mint not in mark_prices]
                if missing_marks:
                    raise ValueError(
                        "backtest_close_mark_price_missing:" + ",".join(sorted(missing_marks))
                    )

            cash_usdc = self._current_cash(
                session=session,
                session_id=session_id,
                fallback=backtest_session.starting_cash_usdc,
            )
            position_value_usdc = 0.0
            realized_pnl_usdc = 0.0
            unrealized_pnl_usdc = 0.0

            for row in positions:
                realized_pnl_usdc += row.realized_pnl_usdc
                if row.net_quantity <= 0:
                    row.unrealized_pnl_usdc = 0.0
                    continue
                mark_price = float(mark_prices[row.mint])
                position_value = row.net_quantity * mark_price
                position_value_usdc += position_value
                row.unrealized_pnl_usdc = position_value - row.cost_basis_usdc
                unrealized_pnl_usdc += row.unrealized_pnl_usdc
                row.last_mark_source = mark_method or backtest_session.mark_method
                row.last_mark_reference = mark_reference
                row.last_mark_price_usdc = mark_price
                row.last_marked_at = closed_at_utc
                row.updated_at = closed_at_utc

            report_row = BacktestSessionReportV1(
                session_id=session_id,
                report_type="session_close",
                cash_usdc=cash_usdc,
                position_value_usdc=position_value_usdc,
                equity_usdc=cash_usdc + position_value_usdc,
                realized_pnl_usdc=realized_pnl_usdc,
                unrealized_pnl_usdc=unrealized_pnl_usdc,
                mark_method=mark_method or backtest_session.mark_method,
                mark_inputs_json=self._encode_json(
                    {
                        "mark_reference": mark_reference,
                        "mark_prices_usdc": mark_prices,
                    }
                ),
                reason_codes_json=self._encode_json(reason_codes or []),
                created_at=closed_at_utc,
            )
            session.add(report_row)

            backtest_session.status = "closed"
            backtest_session.closed_at = closed_at_utc
            backtest_session.ending_cash_usdc = cash_usdc
            backtest_session.reason_codes_json = self._encode_json(reason_codes or [])

            session.commit()
            log.info("backtest_session_closed", session_id=session_id, report_id=report_row.id)
            return {
                "session_id": session_id,
                "report_id": report_row.id,
                "session_status": backtest_session.status,
                "cash_usdc": report_row.cash_usdc,
                "position_value_usdc": report_row.position_value_usdc,
                "equity_usdc": report_row.equity_usdc,
                "realized_pnl_usdc": report_row.realized_pnl_usdc,
                "unrealized_pnl_usdc": report_row.unrealized_pnl_usdc,
                "reason_codes": reason_codes or [],
                "is_scaffold": False,
            }
        finally:
            session.close()

    def _validate_open_inputs(
        self,
        *,
        session_key: str,
        instrument_family: str,
        venue: str,
        base_currency: str,
        bucket_granularity: str,
        fee_bps: int,
        slippage_bps: int,
        latency_ms: int,
        starting_cash_usdc: float,
        mark_method: str,
    ) -> None:
        if not session_key:
            raise ValueError("backtest_session_key_missing")
        if instrument_family != "spot":
            raise ValueError(f"backtest_instrument_family_unsupported:{instrument_family}")
        if venue != "jupiter_spot":
            raise ValueError(f"backtest_venue_unsupported:{venue}")
        if base_currency != "USDC":
            raise ValueError(f"backtest_base_currency_unsupported:{base_currency}")
        if not _GRANULARITY_PATTERN.match(bucket_granularity):
            raise ValueError(f"backtest_bucket_granularity_invalid:{bucket_granularity}")
        if fee_bps < 0 or fee_bps > 10_000:
            raise ValueError("backtest_fee_bps_invalid")
        if slippage_bps < 0 or slippage_bps > 10_000:
            raise ValueError("backtest_slippage_bps_invalid")
        if latency_ms < 0:
            raise ValueError("backtest_latency_ms_invalid")
        if starting_cash_usdc < 0:
            raise ValueError("backtest_starting_cash_invalid")
        if not mark_method:
            raise ValueError("backtest_mark_method_missing")

    def _current_cash(self, *, session, session_id: int, fallback: float) -> float:
        latest_report = (
            session.query(BacktestSessionReportV1)
            .filter_by(session_id=session_id)
            .order_by(
                BacktestSessionReportV1.created_at.desc(),
                BacktestSessionReportV1.id.desc(),
            )
            .first()
        )
        return latest_report.cash_usdc if latest_report is not None else fallback

    def _compute_fee_usdc(
        self,
        *,
        side: str,
        input_amount_int: int,
        output_amount_int: int,
        fee_bps: int,
        mint_decimals: int,
    ) -> float:
        if side == "buy":
            notional_usdc = input_amount_int / (10**_USDC_DECIMALS)
        else:
            del mint_decimals
            notional_usdc = output_amount_int / (10**_USDC_DECIMALS)
        return notional_usdc * (fee_bps / 10_000)

    def _apply_fill(
        self,
        *,
        side: str,
        previous_cash: float,
        position: BacktestPositionV1 | None,
        input_amount_int: int,
        output_amount_int: int,
        mint_decimals: int,
        fee_usdc: float,
    ) -> tuple[float, float, float, float]:
        current_quantity = position.net_quantity if position is not None else 0.0
        current_cost_basis = position.cost_basis_usdc if position is not None else 0.0
        current_realized = position.realized_pnl_usdc if position is not None else 0.0

        if side == "buy":
            notional_usdc = input_amount_int / (10**_USDC_DECIMALS)
            purchased_quantity = output_amount_int / (10**mint_decimals)
            if purchased_quantity <= 0:
                raise ValueError("backtest_fill_output_quantity_invalid")
            total_cash_required = notional_usdc + fee_usdc
            if total_cash_required > previous_cash:
                raise ValueError("backtest_fill_cash_insufficient")
            return (
                previous_cash - total_cash_required,
                current_quantity + purchased_quantity,
                current_cost_basis + total_cash_required,
                current_realized,
            )

        sell_quantity = input_amount_int / (10**mint_decimals)
        if sell_quantity <= 0:
            raise ValueError("backtest_fill_input_quantity_invalid")
        if position is None or current_quantity <= 0:
            raise ValueError("backtest_fill_sell_without_position")
        if sell_quantity > current_quantity:
            raise ValueError("backtest_fill_sell_quantity_exceeds_position")

        proceeds_usdc = output_amount_int / (10**_USDC_DECIMALS)
        cost_portion = current_cost_basis * (sell_quantity / current_quantity)
        remaining_quantity = current_quantity - sell_quantity
        remaining_cost_basis = current_cost_basis - cost_portion
        if remaining_quantity <= 0:
            remaining_quantity = 0.0
            remaining_cost_basis = 0.0
        realized_pnl = current_realized + (proceeds_usdc - fee_usdc - cost_portion)
        return (
            previous_cash + proceeds_usdc - fee_usdc,
            remaining_quantity,
            remaining_cost_basis,
            realized_pnl,
        )

    def _position_value_usdc(self, position: BacktestPositionV1) -> float:
        if position.net_quantity <= 0 or position.last_mark_price_usdc is None:
            return 0.0
        return position.net_quantity * position.last_mark_price_usdc

    def _resolve_token_decimals(self, *, session, mint: str) -> int | None:
        registry_row = session.query(TokenRegistry).filter_by(mint=mint).first()
        if registry_row is not None and registry_row.decimals is not None:
            return int(registry_row.decimals)

        metadata_row = (
            session.query(TokenMetadataSnapshot)
            .filter_by(mint=mint)
            .order_by(TokenMetadataSnapshot.captured_at.desc(), TokenMetadataSnapshot.id.desc())
            .first()
        )
        if metadata_row is not None and metadata_row.decimals is not None:
            return int(metadata_row.decimals)
        return None

    def _normalize_side(self, value: str) -> str | None:
        normalized = value.strip().lower()
        if normalized in {"buy", "sell"}:
            return normalized
        return None

    def _usdc_mint(self) -> str:
        return next(
            mint
            for mint, symbol in self.settings.token_symbol_hints.items()
            if symbol == "USDC"
        )

    def _parse_int(self, value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _encode_json(self, payload: object) -> str:
        return orjson.dumps(payload).decode()
