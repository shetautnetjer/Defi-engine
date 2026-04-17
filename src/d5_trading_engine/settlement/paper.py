"""Paper settlement owner over explicit execution intent and quote truth."""

from __future__ import annotations

from datetime import datetime, timedelta

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ExecutionIntentV1,
    PaperFill,
    PaperPosition,
    PaperSession,
    PaperSessionReport,
    QuoteSnapshot,
    TokenMetadataSnapshot,
    TokenRegistry,
)

log = get_logger(__name__)

_USDC_DECIMALS = 6
_SETTLEMENT_MAX_QUOTE_AGE = timedelta(minutes=5)
_BUY_DIRECTIONS = {"buy", "usdc_to_token"}
_SELL_DIRECTIONS = {"sell", "token_to_usdc"}


class PaperSettlement:
    """Paper settlement service for explicit quote-backed paper fills."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def simulate_fill(
        self,
        *,
        execution_intent_id: int,
        settlement_attempted_at: datetime | None = None,
    ) -> dict[str, object]:
        """Create settlement-owned paper receipts from explicit execution intent."""

        attempted_at = ensure_utc(settlement_attempted_at) or utcnow()
        session_key = self._build_session_key(
            execution_intent_id=execution_intent_id,
            attempted_at=attempted_at,
        )

        session = get_session(self.settings)
        try:
            execution_intent = (
                session.query(ExecutionIntentV1)
                .filter_by(id=execution_intent_id)
                .first()
            )
            quote_snapshot = None
            if execution_intent is not None and execution_intent.quote_snapshot_id is not None:
                quote_snapshot = (
                    session.query(QuoteSnapshot)
                    .filter_by(id=execution_intent.quote_snapshot_id)
                    .first()
                )

            reason_codes = self._validate_inputs(
                execution_intent=execution_intent,
                quote_snapshot=quote_snapshot,
                attempted_at=attempted_at,
            )

            if reason_codes or execution_intent is None or quote_snapshot is None:
                result = self._persist_skipped_session(
                    session=session,
                    session_key=session_key,
                    attempted_at=attempted_at,
                    execution_intent=execution_intent,
                    quote_snapshot=quote_snapshot,
                    reason_codes=reason_codes,
                )
                session.commit()
                return result

            asset_mint = quote_snapshot.output_mint
            asset_decimals = self._resolve_asset_decimals(session=session, mint=asset_mint)
            if asset_decimals is None:
                result = self._persist_skipped_session(
                    session=session,
                    session_key=session_key,
                    attempted_at=attempted_at,
                    quote_snapshot=quote_snapshot,
                    reason_codes=[f"asset_decimals_missing:{asset_mint}"],
                )
                session.commit()
                return result

            fill_metrics = self._build_fill_metrics(
                quote_snapshot=quote_snapshot,
                asset_decimals=asset_decimals,
            )
            if fill_metrics is None:
                result = self._persist_skipped_session(
                    session=session,
                    session_key=session_key,
                    attempted_at=attempted_at,
                    quote_snapshot=quote_snapshot,
                    reason_codes=["quote_amounts_invalid_for_fill"],
                )
                session.commit()
                return result

            paper_session = PaperSession(
                session_key=session_key,
                status="open",
                base_currency="USDC",
                quote_size_lamports=int(quote_snapshot.input_amount),
                opened_at=attempted_at,
                closed_at=None,
                starting_cash_usdc=fill_metrics["cash_usdc"],
                ending_cash_usdc=0.0,
                reason_codes_json=self._encode_json([]),
                created_at=attempted_at,
            )
            session.add(paper_session)
            session.flush()

            paper_fill = PaperFill(
                session_id=paper_session.id,
                execution_intent_id=execution_intent.id,
                risk_verdict_id=execution_intent.risk_verdict_id,
                policy_trace_id=execution_intent.policy_trace_id,
                condition_snapshot_id=execution_intent.condition_snapshot_id,
                source_feature_run_id=execution_intent.source_feature_run_id,
                quote_snapshot_id=quote_snapshot.id,
                policy_state=execution_intent.policy_state,
                risk_state=execution_intent.risk_state,
                request_direction=execution_intent.request_direction,
                input_mint=execution_intent.input_mint,
                output_mint=execution_intent.output_mint,
                input_amount=str(execution_intent.quote_size_lamports),
                output_amount=execution_intent.quoted_output_amount or "0",
                fill_price_usdc=fill_metrics["fill_price_usdc"],
                price_impact_pct=quote_snapshot.price_impact_pct,
                slippage_bps=quote_snapshot.slippage_bps,
                fill_side=execution_intent.intent_side,
                fill_role=execution_intent.intent_role,
                created_at=attempted_at,
            )
            session.add(paper_fill)
            session.flush()

            paper_position = PaperPosition(
                session_id=paper_session.id,
                mint=asset_mint,
                net_quantity=fill_metrics["net_quantity"],
                cost_basis_usdc=fill_metrics["cash_usdc"],
                last_fill_id=paper_fill.id,
                last_mark_source="fill_quote",
                last_mark_quote_snapshot_id=quote_snapshot.id,
                last_mark_price_usdc=fill_metrics["fill_price_usdc"],
                last_marked_at=attempted_at,
                realized_pnl_usdc=0.0,
                unrealized_pnl_usdc=0.0,
                updated_at=attempted_at,
            )
            session.add(paper_position)

            paper_report = PaperSessionReport(
                session_id=paper_session.id,
                report_type="session_snapshot",
                cash_usdc=0.0,
                position_value_usdc=fill_metrics["cash_usdc"],
                equity_usdc=fill_metrics["cash_usdc"],
                realized_pnl_usdc=0.0,
                unrealized_pnl_usdc=0.0,
                mark_method="fill_quote",
                mark_inputs_json=self._encode_json(
                    {
                        "quote_snapshot_id": quote_snapshot.id,
                        "fill_price_usdc": fill_metrics["fill_price_usdc"],
                        "mark_source": "quote_snapshot",
                    }
                ),
                reason_codes_json=self._encode_json([]),
                created_at=attempted_at,
            )
            session.add(paper_report)
            session.commit()

            log.info(
                "paper_fill_created",
                session_id=paper_session.id,
                execution_intent_id=execution_intent.id,
                risk_verdict_id=execution_intent.risk_verdict_id,
                quote_snapshot_id=quote_snapshot.id,
            )
            return {
                "filled": True,
                "session_id": paper_session.id,
                "session_key": paper_session.session_key,
                "session_status": paper_session.status,
                "fill_id": paper_fill.id,
                "position_id": paper_position.id,
                "report_id": paper_report.id,
                "execution_intent_id": execution_intent.id,
                "risk_verdict_id": execution_intent.risk_verdict_id,
                "quote_snapshot_id": quote_snapshot.id,
                "policy_state": execution_intent.policy_state,
                "risk_state": execution_intent.risk_state,
                "reason": "Paper settlement created a quote-backed paper fill from explicit execution intent.",
                "reason_codes": [],
                "is_scaffold": False,
            }
        finally:
            session.close()

    def get_portfolio_state(self, session_key: str | None = None) -> dict[str, object]:
        """Return settlement-owned paper portfolio state for the latest or named session."""

        session = get_session(self.settings)
        try:
            paper_session = self._select_session(session=session, session_key=session_key)
            if paper_session is None:
                return {
                    "session_found": False,
                    "positions": [],
                    "cash_usdc": 0.0,
                    "position_value_usdc": 0.0,
                    "total_value_usdc": 0.0,
                    "is_scaffold": False,
                }

            latest_report = (
                session.query(PaperSessionReport)
                .filter_by(session_id=paper_session.id)
                .order_by(PaperSessionReport.created_at.desc(), PaperSessionReport.id.desc())
                .first()
            )
            positions = (
                session.query(PaperPosition)
                .filter_by(session_id=paper_session.id)
                .order_by(PaperPosition.mint.asc())
                .all()
            )
            return {
                "session_found": True,
                "session_id": paper_session.id,
                "session_key": paper_session.session_key,
                "session_status": paper_session.status,
                "base_currency": paper_session.base_currency,
                "cash_usdc": latest_report.cash_usdc if latest_report else 0.0,
                "position_value_usdc": latest_report.position_value_usdc if latest_report else 0.0,
                "total_value_usdc": latest_report.equity_usdc if latest_report else 0.0,
                "reason_codes": self._decode_json_array(paper_session.reason_codes_json),
                "positions": [
                    {
                        "mint": row.mint,
                        "net_quantity": row.net_quantity,
                        "cost_basis_usdc": row.cost_basis_usdc,
                        "last_fill_id": row.last_fill_id,
                        "last_mark_source": row.last_mark_source,
                        "last_mark_quote_snapshot_id": row.last_mark_quote_snapshot_id,
                        "last_mark_price_usdc": row.last_mark_price_usdc,
                        "realized_pnl_usdc": row.realized_pnl_usdc,
                        "unrealized_pnl_usdc": row.unrealized_pnl_usdc,
                    }
                    for row in positions
                ],
                "is_scaffold": False,
            }
        finally:
            session.close()

    def _validate_inputs(
        self,
        *,
        execution_intent: ExecutionIntentV1 | None,
        quote_snapshot: QuoteSnapshot | None,
        attempted_at: datetime,
    ) -> list[str]:
        reason_codes: list[str] = []
        if execution_intent is None:
            reason_codes.append("execution_intent_missing")
            return reason_codes
        if execution_intent.intent_state != "ready":
            reason_codes.append(f"execution_intent_not_ready:{execution_intent.intent_state}")
            reason_codes.extend(self._decode_json_array(execution_intent.reason_codes_json))
            return reason_codes
        if quote_snapshot is None:
            reason_codes.append("execution_intent_quote_snapshot_missing")
            return reason_codes

        if execution_intent.quote_snapshot_id != quote_snapshot.id:
            reason_codes.append("execution_intent_quote_snapshot_mismatch")
        if execution_intent.risk_verdict_id is None:
            reason_codes.append("execution_intent_risk_verdict_missing")
        if execution_intent.policy_trace_id is None:
            reason_codes.append("execution_intent_policy_trace_missing")
        if execution_intent.request_direction != "usdc_to_token":
            reason_codes.append(
                f"execution_intent_direction_unsupported:{execution_intent.request_direction}"
            )
        if execution_intent.intent_side != "buy":
            reason_codes.append(
                f"execution_intent_side_unsupported:{execution_intent.intent_side}"
            )
        if execution_intent.input_mint != quote_snapshot.input_mint:
            reason_codes.append("execution_intent_input_mint_mismatch")
        if execution_intent.output_mint != quote_snapshot.output_mint:
            reason_codes.append("execution_intent_output_mint_mismatch")
        if execution_intent.quote_size_lamports != self._parse_int(quote_snapshot.input_amount):
            reason_codes.append("execution_intent_quote_size_mismatch")
        if execution_intent.quoted_output_amount != quote_snapshot.output_amount:
            reason_codes.append("execution_intent_quote_output_mismatch")

        quote_timestamp = ensure_utc(quote_snapshot.captured_at) or ensure_utc(
            quote_snapshot.requested_at
        )
        if quote_timestamp is None:
            reason_codes.append("execution_intent_quote_timestamp_missing")
        else:
            if quote_timestamp > attempted_at:
                reason_codes.append("settlement_quote_after_attempt")
            elif (attempted_at - quote_timestamp) > _SETTLEMENT_MAX_QUOTE_AGE:
                reason_codes.append("settlement_quote_stale")
        return reason_codes

    def _persist_skipped_session(
        self,
        *,
        session,
        session_key: str,
        attempted_at: datetime,
        execution_intent: ExecutionIntentV1 | None,
        quote_snapshot: QuoteSnapshot | None,
        reason_codes: list[str],
    ) -> dict[str, object]:
        normalized_direction = self._normalize_direction(
            (
                execution_intent.request_direction
                if execution_intent is not None
                else quote_snapshot.request_direction if quote_snapshot is not None else None
            )
        )
        attempt_cash_usdc = self._derive_attempt_cash_usdc(
            quote_snapshot=quote_snapshot,
            normalized_direction=normalized_direction,
        )
        quote_size_lamports = (
            self._parse_int(quote_snapshot.input_amount)
            if quote_snapshot is not None
            else None
        )
        paper_session = PaperSession(
            session_key=session_key,
            status="skipped",
            base_currency="USDC",
            quote_size_lamports=quote_size_lamports or 0,
            opened_at=attempted_at,
            closed_at=attempted_at,
            starting_cash_usdc=attempt_cash_usdc,
            ending_cash_usdc=attempt_cash_usdc,
            reason_codes_json=self._encode_json(reason_codes),
            created_at=attempted_at,
        )
        session.add(paper_session)
        session.flush()

        paper_report = PaperSessionReport(
            session_id=paper_session.id,
            report_type="session_close",
            cash_usdc=attempt_cash_usdc,
            position_value_usdc=0.0,
            equity_usdc=attempt_cash_usdc,
            realized_pnl_usdc=0.0,
            unrealized_pnl_usdc=0.0,
            mark_method="none",
            mark_inputs_json=self._encode_json({}),
            reason_codes_json=self._encode_json(reason_codes),
            created_at=attempted_at,
        )
        session.add(paper_report)
        return {
            "filled": False,
            "session_id": paper_session.id,
            "session_key": paper_session.session_key,
            "session_status": paper_session.status,
            "fill_id": None,
            "position_id": None,
            "report_id": paper_report.id,
            "execution_intent_id": execution_intent.id if execution_intent is not None else None,
            "risk_verdict_id": (
                execution_intent.risk_verdict_id if execution_intent is not None else None
            ),
            "quote_snapshot_id": quote_snapshot.id if quote_snapshot is not None else None,
            "reason": self._summarize_skip(reason_codes),
            "reason_codes": reason_codes,
            "is_scaffold": False,
        }

    def _build_fill_metrics(
        self,
        *,
        quote_snapshot: QuoteSnapshot,
        asset_decimals: int,
    ) -> dict[str, float] | None:
        input_amount = self._parse_int(quote_snapshot.input_amount)
        output_amount = self._parse_int(quote_snapshot.output_amount)
        if input_amount is None or output_amount in (None, 0):
            return None

        cash_usdc = input_amount / (10**_USDC_DECIMALS)
        net_quantity = output_amount / (10**asset_decimals)
        if net_quantity <= 0:
            return None
        fill_price_usdc = cash_usdc / net_quantity
        return {
            "cash_usdc": cash_usdc,
            "net_quantity": net_quantity,
            "fill_price_usdc": fill_price_usdc,
        }

    def _resolve_asset_decimals(self, *, session, mint: str) -> int | None:
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

    def _select_session(self, *, session, session_key: str | None) -> PaperSession | None:
        query = session.query(PaperSession)
        if session_key is not None:
            return query.filter_by(session_key=session_key).first()
        return query.order_by(PaperSession.created_at.desc(), PaperSession.id.desc()).first()

    def _derive_attempt_cash_usdc(
        self,
        *,
        quote_snapshot: QuoteSnapshot | None,
        normalized_direction: str | None,
    ) -> float:
        if quote_snapshot is None or normalized_direction != "usdc_to_token":
            return 0.0
        input_amount = self._parse_int(quote_snapshot.input_amount)
        if input_amount is None:
            return 0.0
        return input_amount / (10**_USDC_DECIMALS)

    def _build_session_key(
        self,
        *,
        execution_intent_id: int,
        attempted_at: datetime,
    ) -> str:
        return (
            "paper_"
            f"{attempted_at.strftime('%Y%m%dT%H%M%S%fZ')}_"
            f"intent{execution_intent_id}"
        )

    def _normalize_direction(self, value: str | None) -> str | None:
        if value in _BUY_DIRECTIONS:
            return "usdc_to_token"
        if value in _SELL_DIRECTIONS:
            return "token_to_usdc"
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

    def _decode_json_array(self, payload: str) -> list[str]:
        try:
            decoded = orjson.loads(payload)
        except orjson.JSONDecodeError:
            return ["paper_session_payload_malformed"]
        if not isinstance(decoded, list):
            return ["paper_session_payload_malformed"]
        return [str(item) for item in decoded]

    def _summarize_skip(self, reason_codes: list[str]) -> str:
        joined = ", ".join(reason_codes)
        return (
            "Paper settlement skipped because the explicit execution intent "
            f"or its quote provenance was incompatible: {joined}"
        )
