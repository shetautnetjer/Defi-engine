"""Execution intent owner — bounded paper-only spot intent selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ExecutionIntentV1,
    QuoteSnapshot,
    RiskGlobalRegimeGateV1,
)

log = get_logger(__name__)

IntentState = Literal["ready", "rejected"]

_INTENT_MAX_QUOTE_AGE = timedelta(minutes=5)
_BUY_DIRECTIONS = {"buy", "usdc_to_token"}
_SELL_DIRECTIONS = {"sell", "token_to_usdc"}


@dataclass(frozen=True)
class EvaluatedExecutionIntent:
    """In-memory execution-intent decision before persistence."""

    intent_state: IntentState
    reason_codes: list[str]
    trace_payload: dict[str, object]


class ExecutionIntentOwner:
    """Bounded paper-only owner that turns risk truth into explicit spot intent."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def create_spot_intent(
        self,
        *,
        risk_verdict_id: int,
        quote_snapshot_id: int,
        intent_created_at: datetime | None = None,
    ) -> dict[str, object]:
        """Persist explicit spot execution intent from risk and quote truth."""

        created_at = ensure_utc(intent_created_at) or utcnow()
        intent_key = self._build_intent_key(
            risk_verdict_id=risk_verdict_id,
            quote_snapshot_id=quote_snapshot_id,
            created_at=created_at,
        )

        session = get_session(self.settings)
        try:
            risk_verdict = (
                session.query(RiskGlobalRegimeGateV1)
                .filter_by(id=risk_verdict_id)
                .first()
            )
            quote_snapshot = (
                session.query(QuoteSnapshot)
                .filter_by(id=quote_snapshot_id)
                .first()
            )
            evaluated = self._evaluate_inputs(
                risk_verdict=risk_verdict,
                quote_snapshot=quote_snapshot,
                created_at=created_at,
            )
            intent_row = ExecutionIntentV1(
                intent_key=intent_key,
                risk_verdict_id=risk_verdict.id if risk_verdict is not None else None,
                policy_trace_id=risk_verdict.policy_trace_id if risk_verdict is not None else None,
                condition_snapshot_id=(
                    risk_verdict.condition_snapshot_id if risk_verdict is not None else None
                ),
                source_feature_run_id=(
                    risk_verdict.source_feature_run_id if risk_verdict is not None else None
                ),
                quote_snapshot_id=quote_snapshot.id if quote_snapshot is not None else None,
                bucket_start_utc=(
                    risk_verdict.bucket_start_utc if risk_verdict is not None else None
                ),
                intent_state=evaluated.intent_state,
                venue=(quote_snapshot.provider if quote_snapshot is not None else "unknown"),
                settlement_model="paper_spot_v1",
                strategy_family="global_regime_v1",
                policy_state=(risk_verdict.policy_state if risk_verdict is not None else None),
                risk_state=(risk_verdict.risk_state if risk_verdict is not None else None),
                request_direction=(
                    self._normalize_direction(quote_snapshot.request_direction)
                    if quote_snapshot is not None
                    else None
                ),
                intent_side=(
                    self._intent_side(quote_snapshot.request_direction)
                    if quote_snapshot is not None
                    else None
                ),
                intent_role="entry",
                entry_intent="quote_backed_spot_entry",
                exit_intent="not_owned",
                stop_intent="not_owned",
                input_mint=(quote_snapshot.input_mint if quote_snapshot is not None else None),
                output_mint=(quote_snapshot.output_mint if quote_snapshot is not None else None),
                quote_size_lamports=(
                    self._parse_int(quote_snapshot.input_amount)
                    if quote_snapshot is not None
                    else None
                ),
                quoted_output_amount=(
                    quote_snapshot.output_amount if quote_snapshot is not None else None
                ),
                reason_codes_json=self._encode_json(evaluated.reason_codes),
                trace_json=self._encode_json(evaluated.trace_payload),
                created_at=created_at,
            )
            session.add(intent_row)
            session.commit()
            session.refresh(intent_row)
            log.info(
                "execution_intent_persisted",
                execution_intent_id=intent_row.id,
                intent_state=intent_row.intent_state,
                risk_verdict_id=intent_row.risk_verdict_id,
                quote_snapshot_id=intent_row.quote_snapshot_id,
            )
            return self._serialize_intent(intent_row)
        finally:
            session.close()

    def _evaluate_inputs(
        self,
        *,
        risk_verdict: RiskGlobalRegimeGateV1 | None,
        quote_snapshot: QuoteSnapshot | None,
        created_at: datetime,
    ) -> EvaluatedExecutionIntent:
        reason_codes: list[str] = []
        normalized_direction = self._normalize_direction(
            quote_snapshot.request_direction if quote_snapshot is not None else None
        )
        trace_payload: dict[str, object] = {
            "intent_scope": {
                "paper_only": True,
                "settlement_model": "paper_spot_v1",
                "strategy_family": "global_regime_v1",
                "entry_intent": "quote_backed_spot_entry",
                "exit_intent": "not_owned",
                "stop_intent": "not_owned",
            },
            "risk_input": {
                "risk_verdict_id": risk_verdict.id if risk_verdict is not None else None,
                "policy_trace_id": (
                    risk_verdict.policy_trace_id if risk_verdict is not None else None
                ),
                "policy_state": (
                    risk_verdict.policy_state if risk_verdict is not None else None
                ),
                "risk_state": risk_verdict.risk_state if risk_verdict is not None else None,
                "bucket_start_utc": (
                    risk_verdict.bucket_start_utc.isoformat()
                    if risk_verdict is not None
                    else None
                ),
            },
            "quote_input": {
                "quote_snapshot_id": quote_snapshot.id if quote_snapshot is not None else None,
                "provider": quote_snapshot.provider if quote_snapshot is not None else None,
                "request_direction": normalized_direction,
                "input_mint": quote_snapshot.input_mint if quote_snapshot is not None else None,
                "output_mint": quote_snapshot.output_mint if quote_snapshot is not None else None,
                "input_amount": (
                    quote_snapshot.input_amount if quote_snapshot is not None else None
                ),
                "output_amount": (
                    quote_snapshot.output_amount if quote_snapshot is not None else None
                ),
            },
        }

        if risk_verdict is None:
            reason_codes.append("risk_verdict_missing")
        else:
            if risk_verdict.risk_state != "allowed":
                reason_codes.append(f"risk_state_not_allowed:{risk_verdict.risk_state}")
            if int(risk_verdict.unresolved_input_flag or 0) != 0:
                reason_codes.append("risk_unresolved_input")
            if int(risk_verdict.stale_data_authorized_flag or 0) != 1:
                reason_codes.append("risk_stale_data_not_authorized")
            if risk_verdict.policy_state != "eligible_long":
                reason_codes.append(
                    "policy_state_unsupported_for_spot_intent:"
                    f"{risk_verdict.policy_state}"
                )

        if quote_snapshot is None:
            reason_codes.append("quote_snapshot_missing")
        else:
            if normalized_direction is None:
                reason_codes.append("quote_request_direction_unsupported")
            elif normalized_direction != "usdc_to_token":
                reason_codes.append(f"quote_direction_incompatible:{normalized_direction}")

            usdc_mint = self._usdc_mint()
            tracked_universe = set(self.settings.token_universe)
            if (
                quote_snapshot.input_mint not in tracked_universe
                or quote_snapshot.output_mint not in tracked_universe
            ):
                reason_codes.append("quote_outside_tracked_universe")
            if (
                quote_snapshot.input_mint != usdc_mint
                or quote_snapshot.output_mint == usdc_mint
            ):
                reason_codes.append("quote_not_supported_spot_buy_pair")

            quote_timestamp = ensure_utc(quote_snapshot.captured_at) or ensure_utc(
                quote_snapshot.requested_at
            )
            trace_payload["quote_input"]["quote_timestamp_utc"] = (
                quote_timestamp.isoformat() if quote_timestamp is not None else None
            )
            if quote_timestamp is None:
                reason_codes.append("quote_timestamp_missing")
            else:
                if quote_timestamp > created_at:
                    reason_codes.append("execution_intent_quote_after_creation")
                elif (created_at - quote_timestamp) > _INTENT_MAX_QUOTE_AGE:
                    reason_codes.append("execution_intent_quote_stale")

            quote_size = self._parse_int(quote_snapshot.input_amount)
            if quote_size is None:
                reason_codes.append("quote_input_amount_invalid")
            elif quote_size not in set(self.settings.quote_amounts_lamports):
                reason_codes.append("quote_size_not_configured")

            if self._parse_int(quote_snapshot.output_amount) in (None, 0):
                reason_codes.append("quote_output_amount_invalid")

        trace_payload["decision"] = {
            "intent_state": "ready" if not reason_codes else "rejected",
            "reason_codes": reason_codes,
        }
        return EvaluatedExecutionIntent(
            intent_state="ready" if not reason_codes else "rejected",
            reason_codes=reason_codes,
            trace_payload=trace_payload,
        )

    def _serialize_intent(self, intent_row: ExecutionIntentV1) -> dict[str, object]:
        reason_codes = self._decode_json_array(intent_row.reason_codes_json)
        return {
            "execution_intent_id": intent_row.id,
            "intent_key": intent_row.intent_key,
            "intent_state": intent_row.intent_state,
            "ready": intent_row.intent_state == "ready",
            "risk_verdict_id": intent_row.risk_verdict_id,
            "quote_snapshot_id": intent_row.quote_snapshot_id,
            "policy_trace_id": intent_row.policy_trace_id,
            "condition_snapshot_id": intent_row.condition_snapshot_id,
            "source_feature_run_id": intent_row.source_feature_run_id,
            "input_mint": intent_row.input_mint,
            "output_mint": intent_row.output_mint,
            "quote_size_lamports": intent_row.quote_size_lamports,
            "quoted_output_amount": intent_row.quoted_output_amount,
            "intent_side": intent_row.intent_side,
            "intent_role": intent_row.intent_role,
            "settlement_model": intent_row.settlement_model,
            "reason": self._summarize_reason(intent_row.intent_state, reason_codes),
            "reason_codes": reason_codes,
            "is_scaffold": False,
        }

    def _build_intent_key(
        self,
        *,
        risk_verdict_id: int,
        quote_snapshot_id: int,
        created_at: datetime,
    ) -> str:
        return (
            "exec_"
            f"{created_at.strftime('%Y%m%dT%H%M%S%fZ')}_"
            f"risk{risk_verdict_id}_quote{quote_snapshot_id}"
        )

    def _normalize_direction(self, value: str | None) -> str | None:
        if value in _BUY_DIRECTIONS:
            return "usdc_to_token"
        if value in _SELL_DIRECTIONS:
            return "token_to_usdc"
        return None

    def _intent_side(self, value: str | None) -> str | None:
        normalized = self._normalize_direction(value)
        if normalized == "usdc_to_token":
            return "buy"
        if normalized == "token_to_usdc":
            return "sell"
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
            return ["execution_intent_payload_malformed"]
        if not isinstance(decoded, list):
            return ["execution_intent_payload_malformed"]
        return [str(item) for item in decoded]

    def _summarize_reason(self, intent_state: IntentState, reason_codes: list[str]) -> str:
        if intent_state == "ready":
            return (
                "Execution intent selected a bounded paper-only quote-backed "
                "spot entry for settlement."
            )
        joined = ", ".join(reason_codes)
        return f"Execution intent rejected the proposed spot action: {joined}"
