"""Risk gate — hard vetoes, halts, and conservative controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    FeatureMaterializationRun,
    PolicyGlobalRegimeTraceV1,
    RiskGlobalRegimeGateV1,
)

log = get_logger(__name__)

RiskState = Literal["allowed", "no_trade", "halted"]
AnomalySignalState = Literal["not_owned", "clear", "anomalous", "unresolved"]


@dataclass(frozen=True)
class EvaluatedRiskVerdict:
    """In-memory risk verdict before persistence."""

    risk_state: RiskState
    reason_codes: list[str]
    vetoes: list[str]
    stale_data_authorized: bool
    unresolved_input: bool
    anomaly_signal_state: AnomalySignalState
    trace_payload: dict[str, object]


@dataclass(frozen=True)
class FreshnessAuthorization:
    """Parsed freshness authorization state from the upstream feature receipt."""

    authorized: bool
    blocking_lanes: list[str]
    required_lane_states: dict[str, dict[str, object]]


class RiskGate:
    """Final veto owner over persisted policy truth."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def evaluate_global_regime_v1(self, *, policy_trace_id: int | None = None) -> dict[str, object]:
        """Evaluate the first explicit hard risk gate over persisted policy truth."""

        session = get_session(self.settings)
        try:
            policy_trace = self._select_policy_trace(
                session=session,
                policy_trace_id=policy_trace_id,
            )
            if policy_trace is None:
                return self._build_ephemeral_verdict(
                    reason_codes=["policy_trace_missing"],
                    vetoes=["policy_trace_missing"],
                    policy_trace_id=policy_trace_id,
                )

            feature_run = self._load_feature_run(
                session=session,
                run_id=policy_trace.source_feature_run_id,
            )
            evaluated = self._evaluate_policy_trace(
                policy_trace=policy_trace,
                feature_run=feature_run,
            )
            verdict_row = self._persist_verdict(
                session=session,
                policy_trace=policy_trace,
                evaluated=evaluated,
            )
            session.commit()
            session.refresh(verdict_row)
            return self._serialize_verdict(verdict_row)
        finally:
            session.close()

    def check_trade(self, proposal: dict[str, Any]) -> dict[str, object]:
        """Fail closed unless a policy trace is supplied for risk evaluation."""

        policy_trace_id = proposal.get("policy_trace_id")
        if policy_trace_id is None:
            return self._build_ephemeral_verdict(
                reason_codes=[
                    "trade_proposal_missing_policy_trace_id",
                    "settlement_surface_not_owned",
                ],
                vetoes=["trade_proposal_missing_policy_trace_id"],
            )
        try:
            resolved_policy_trace_id = int(policy_trace_id)
        except (TypeError, ValueError):
            return self._build_ephemeral_verdict(
                reason_codes=["trade_proposal_invalid_policy_trace_id"],
                vetoes=["trade_proposal_invalid_policy_trace_id"],
            )
        return self.evaluate_global_regime_v1(policy_trace_id=resolved_policy_trace_id)

    def emergency_halt(self) -> bool:
        """Operator halt is not owned yet in the first accepted risk slice."""

        return False

    def _select_policy_trace(
        self,
        *,
        session,
        policy_trace_id: int | None,
    ) -> PolicyGlobalRegimeTraceV1 | None:
        if policy_trace_id is not None:
            return session.query(PolicyGlobalRegimeTraceV1).filter_by(id=policy_trace_id).first()
        return (
            session.query(PolicyGlobalRegimeTraceV1)
            .order_by(
                PolicyGlobalRegimeTraceV1.created_at.desc(),
                PolicyGlobalRegimeTraceV1.id.desc(),
            )
            .first()
        )

    def _load_feature_run(
        self,
        *,
        session,
        run_id: str,
    ) -> FeatureMaterializationRun | None:
        return session.query(FeatureMaterializationRun).filter_by(run_id=run_id).first()

    def _evaluate_policy_trace(
        self,
        *,
        policy_trace: PolicyGlobalRegimeTraceV1,
        feature_run: FeatureMaterializationRun | None,
    ) -> EvaluatedRiskVerdict:
        base_trace = {
            "policy_input": {
                "policy_trace_id": policy_trace.id,
                "condition_run_id": policy_trace.condition_run_id,
                "condition_snapshot_id": policy_trace.condition_snapshot_id,
                "source_feature_run_id": policy_trace.source_feature_run_id,
                "bucket_start_utc": policy_trace.bucket_start_utc.isoformat(),
                "policy_state": policy_trace.policy_state,
                "macro_context_state": policy_trace.macro_context_state,
                "condition_blocked_flag": bool(policy_trace.condition_blocked_flag),
                "condition_blocking_reason": policy_trace.condition_blocking_reason,
            },
            "anomaly_signal_state": "not_owned",
        }

        if feature_run is None:
            return EvaluatedRiskVerdict(
                risk_state="halted",
                reason_codes=["missing_feature_run"],
                vetoes=["missing_feature_run"],
                stale_data_authorized=False,
                unresolved_input=True,
                anomaly_signal_state="not_owned",
                trace_payload={
                    **base_trace,
                    "freshness_authorization": {
                        "authorized": False,
                        "blocking_lanes": [],
                        "required_lanes": {},
                    },
                },
            )

        freshness_authorization, freshness_error = self._parse_freshness_authorization(
            feature_run=feature_run,
        )
        if freshness_error is not None:
            return EvaluatedRiskVerdict(
                risk_state="halted",
                reason_codes=[freshness_error],
                vetoes=[freshness_error],
                stale_data_authorized=False,
                unresolved_input=True,
                anomaly_signal_state="not_owned",
                trace_payload={
                    **base_trace,
                    "freshness_authorization": {
                        "authorized": False,
                        "blocking_lanes": [],
                        "required_lanes": {},
                    },
                },
            )

        assert freshness_authorization is not None
        trace_payload = {
            **base_trace,
            "freshness_authorization": {
                "authorized": freshness_authorization.authorized,
                "blocking_lanes": freshness_authorization.blocking_lanes,
                "required_lanes": freshness_authorization.required_lane_states,
            },
        }

        if not freshness_authorization.authorized:
            reason_codes = [
                f"required_lane_downstream_ineligible:{lane_name}"
                for lane_name in freshness_authorization.blocking_lanes
            ]
            return EvaluatedRiskVerdict(
                risk_state="halted",
                reason_codes=reason_codes,
                vetoes=reason_codes,
                stale_data_authorized=False,
                unresolved_input=False,
                anomaly_signal_state="not_owned",
                trace_payload=trace_payload,
            )

        if bool(policy_trace.condition_blocked_flag):
            reason_codes = ["condition_blocked_flag"]
            if policy_trace.condition_blocking_reason:
                reason_codes.append(
                    f"condition_blocking_reason:{policy_trace.condition_blocking_reason}"
                )
            return EvaluatedRiskVerdict(
                risk_state="no_trade",
                reason_codes=reason_codes,
                vetoes=["condition_blocked_flag"],
                stale_data_authorized=True,
                unresolved_input=False,
                anomaly_signal_state="not_owned",
                trace_payload=trace_payload,
            )

        if policy_trace.policy_state == "no_trade":
            return EvaluatedRiskVerdict(
                risk_state="no_trade",
                reason_codes=["policy_state:no_trade"],
                vetoes=["policy_state:no_trade"],
                stale_data_authorized=True,
                unresolved_input=False,
                anomaly_signal_state="not_owned",
                trace_payload=trace_payload,
            )

        return EvaluatedRiskVerdict(
            risk_state="allowed",
            reason_codes=[f"policy_state:{policy_trace.policy_state}"],
            vetoes=[],
            stale_data_authorized=True,
            unresolved_input=False,
            anomaly_signal_state="not_owned",
            trace_payload=trace_payload,
        )

    def _parse_freshness_authorization(
        self,
        *,
        feature_run: FeatureMaterializationRun,
    ) -> tuple[FreshnessAuthorization | None, str | None]:
        if feature_run.freshness_snapshot_json is None:
            return None, "freshness_snapshot_missing"
        try:
            raw_payload = orjson.loads(feature_run.freshness_snapshot_json)
        except orjson.JSONDecodeError:
            return None, "freshness_snapshot_malformed"
        if not isinstance(raw_payload, dict):
            return None, "freshness_snapshot_malformed"

        raw_required_lanes = raw_payload.get("required_lanes")
        if not isinstance(raw_required_lanes, dict):
            return None, "freshness_snapshot_malformed"

        blocking_lanes: list[str] = []
        required_lane_states: dict[str, dict[str, object]] = {}
        for lane_name, lane_state in raw_required_lanes.items():
            if not isinstance(lane_name, str) or not isinstance(lane_state, dict):
                return None, "freshness_snapshot_malformed"
            required_for_authorization = lane_state.get("required_for_authorization")
            downstream_eligible = lane_state.get("downstream_eligible")
            freshness_state = lane_state.get("freshness_state")
            if not isinstance(required_for_authorization, bool):
                return None, "freshness_snapshot_malformed"
            if not isinstance(downstream_eligible, bool):
                return None, "freshness_snapshot_malformed"
            if not isinstance(freshness_state, str):
                return None, "freshness_snapshot_malformed"
            required_lane_states[lane_name] = {
                "required_for_authorization": required_for_authorization,
                "downstream_eligible": downstream_eligible,
                "freshness_state": freshness_state,
                "latest_error_summary": lane_state.get("latest_error_summary"),
            }
            if required_for_authorization and not downstream_eligible:
                blocking_lanes.append(lane_name)

        return (
            FreshnessAuthorization(
                authorized=not blocking_lanes,
                blocking_lanes=blocking_lanes,
                required_lane_states=required_lane_states,
            ),
            None,
        )

    def _persist_verdict(
        self,
        *,
        session,
        policy_trace: PolicyGlobalRegimeTraceV1,
        evaluated: EvaluatedRiskVerdict,
    ) -> RiskGlobalRegimeGateV1:
        verdict_row = RiskGlobalRegimeGateV1(
            policy_trace_id=policy_trace.id,
            condition_run_id=policy_trace.condition_run_id,
            condition_snapshot_id=policy_trace.condition_snapshot_id,
            source_feature_run_id=policy_trace.source_feature_run_id,
            bucket_start_utc=policy_trace.bucket_start_utc,
            policy_state=policy_trace.policy_state,
            risk_state=evaluated.risk_state,
            macro_context_state=policy_trace.macro_context_state,
            condition_blocked_flag=int(policy_trace.condition_blocked_flag or 0),
            stale_data_authorized_flag=int(evaluated.stale_data_authorized),
            unresolved_input_flag=int(evaluated.unresolved_input),
            anomaly_signal_state=evaluated.anomaly_signal_state,
            reason_codes_json=orjson.dumps(evaluated.reason_codes).decode(),
            trace_json=orjson.dumps(evaluated.trace_payload).decode(),
            created_at=utcnow(),
        )
        session.add(verdict_row)
        return verdict_row

    def _serialize_verdict(self, verdict_row: RiskGlobalRegimeGateV1) -> dict[str, object]:
        reason_codes = self._decode_json_array(verdict_row.reason_codes_json)
        vetoes = [] if verdict_row.risk_state == "allowed" else reason_codes
        return {
            "risk_verdict_id": verdict_row.id,
            "allowed": verdict_row.risk_state == "allowed",
            "risk_state": verdict_row.risk_state,
            "halted": verdict_row.risk_state == "halted",
            "policy_trace_id": verdict_row.policy_trace_id,
            "condition_run_id": verdict_row.condition_run_id,
            "source_feature_run_id": verdict_row.source_feature_run_id,
            "bucket_start_utc": verdict_row.bucket_start_utc.isoformat(),
            "reason": self._summarize_reason(verdict_row.risk_state, reason_codes),
            "reason_codes": reason_codes,
            "vetoes": vetoes,
            "anomaly_signal_state": verdict_row.anomaly_signal_state,
            "is_scaffold": False,
        }

    def _build_ephemeral_verdict(
        self,
        *,
        reason_codes: list[str],
        vetoes: list[str],
        policy_trace_id: int | None = None,
    ) -> dict[str, object]:
        return {
            "risk_verdict_id": None,
            "allowed": False,
            "risk_state": "halted",
            "halted": True,
            "policy_trace_id": policy_trace_id,
            "condition_run_id": None,
            "source_feature_run_id": None,
            "bucket_start_utc": None,
            "reason": self._summarize_reason("halted", reason_codes),
            "reason_codes": reason_codes,
            "vetoes": vetoes,
            "anomaly_signal_state": "not_owned",
            "is_scaffold": False,
        }

    def _decode_json_array(self, payload: str) -> list[str]:
        try:
            decoded = orjson.loads(payload)
        except orjson.JSONDecodeError:
            return ["risk_verdict_payload_malformed"]
        if not isinstance(decoded, list):
            return ["risk_verdict_payload_malformed"]
        return [str(item) for item in decoded]

    def _summarize_reason(self, risk_state: RiskState, reason_codes: list[str]) -> str:
        if risk_state == "allowed":
            return "Risk gate found no hard vetoes for the selected policy trace."
        if risk_state == "no_trade":
            joined = ", ".join(reason_codes)
            return f"Risk gate preserved a no-trade outcome: {joined}"
        joined = ", ".join(reason_codes)
        return f"Risk gate halted because repo-owned inputs were unresolved: {joined}"
