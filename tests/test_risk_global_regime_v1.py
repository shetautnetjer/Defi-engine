from __future__ import annotations

import json
from datetime import timedelta

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.policy.global_regime_v1 import GlobalRegimePolicyEvaluator
from d5_trading_engine.risk.gate import RiskGate
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    FeatureMaterializationRun,
    PolicyGlobalRegimeTraceV1,
    RiskGlobalRegimeGateV1,
)


def _freshness_snapshot(
    *,
    lane_overrides: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    base_lanes = {
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
        "fred-observations": {
            "required_for_authorization": False,
            "downstream_eligible": False,
            "freshness_state": "degraded",
            "latest_error_summary": "missing provider health receipt",
        },
    }
    if lane_overrides:
        for lane_name, override in lane_overrides.items():
            base_lanes.setdefault(lane_name, {}).update(override)
    blocking_lanes = [
        f"{lane_name}={lane_state['freshness_state']}"
        for lane_name, lane_state in base_lanes.items()
        if lane_state["required_for_authorization"] and not lane_state["downstream_eligible"]
    ]
    return {
        "generated_at_utc": utcnow().isoformat(),
        "required_lanes": base_lanes,
        "authorized": not blocking_lanes,
        "blocking_lanes": blocking_lanes,
    }


def _seed_policy_trace(
    settings,
    *,
    run_id: str,
    semantic_regime: str,
    blocked_flag: int = 0,
    blocking_reason: str | None = None,
    freshness_snapshot_json: str | None = None,
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
                freshness_snapshot_json=freshness_snapshot_json,
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
                blocked_flag=blocked_flag,
                blocking_reason=blocking_reason,
                model_family="gaussian_hmm_4state",
                macro_context_state="degraded",
                created_at=finished_at,
            )
        )
        session.commit()
    finally:
        session.close()
    return GlobalRegimePolicyEvaluator(settings).evaluate(condition_run_id=run_id)["trace_id"]


def test_risk_gate_allows_eligible_policy_trace_with_healthy_required_lanes(settings) -> None:
    run_migrations_to_head(settings)
    trace_id = _seed_policy_trace(
        settings,
        run_id="risk_allowed",
        semantic_regime="long_friendly",
        freshness_snapshot_json=json.dumps(_freshness_snapshot()),
    )

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)

    assert result["allowed"] is True
    assert result["risk_state"] == "allowed"
    assert result["halted"] is False
    assert result["policy_trace_id"] == trace_id
    assert result["anomaly_signal_state"] == "not_owned"
    assert result["is_scaffold"] is False

    session = get_session(settings)
    try:
        verdict = session.query(RiskGlobalRegimeGateV1).one()
    finally:
        session.close()

    assert verdict.policy_trace_id == trace_id
    assert verdict.policy_state == "eligible_long"
    assert verdict.risk_state == "allowed"
    assert verdict.macro_context_state == "degraded"
    assert verdict.stale_data_authorized_flag == 1
    assert verdict.unresolved_input_flag == 0
    assert verdict.anomaly_signal_state == "not_owned"


def test_risk_gate_preserves_policy_no_trade(settings) -> None:
    run_migrations_to_head(settings)
    trace_id = _seed_policy_trace(
        settings,
        run_id="risk_no_trade",
        semantic_regime="risk_off",
        freshness_snapshot_json=json.dumps(_freshness_snapshot()),
    )

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)

    assert result["allowed"] is False
    assert result["risk_state"] == "no_trade"
    assert result["halted"] is False
    assert "policy_state:no_trade" in result["reason_codes"]


def test_risk_gate_preserves_condition_blocked_flag(settings) -> None:
    run_migrations_to_head(settings)
    trace_id = _seed_policy_trace(
        settings,
        run_id="risk_condition_blocked",
        semantic_regime="long_friendly",
        blocked_flag=1,
        blocking_reason="risk_off",
        freshness_snapshot_json=json.dumps(_freshness_snapshot()),
    )

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)

    assert result["allowed"] is False
    assert result["risk_state"] == "no_trade"
    assert result["halted"] is False
    assert "condition_blocked_flag" in result["reason_codes"]
    assert "condition_blocking_reason:risk_off" in result["reason_codes"]


def test_risk_gate_halts_when_policy_trace_is_missing(settings) -> None:
    run_migrations_to_head(settings)

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=99999)

    assert result["allowed"] is False
    assert result["risk_state"] == "halted"
    assert result["halted"] is True
    assert result["risk_verdict_id"] is None
    assert result["reason_codes"] == ["policy_trace_missing"]

    session = get_session(settings)
    try:
        assert session.query(RiskGlobalRegimeGateV1).count() == 0
    finally:
        session.close()


def test_risk_gate_halts_when_freshness_snapshot_is_missing(settings) -> None:
    run_migrations_to_head(settings)
    trace_id = _seed_policy_trace(
        settings,
        run_id="risk_missing_snapshot",
        semantic_regime="long_friendly",
        freshness_snapshot_json=None,
    )

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)

    assert result["allowed"] is False
    assert result["risk_state"] == "halted"
    assert result["halted"] is True
    assert result["reason_codes"] == ["freshness_snapshot_missing"]


def test_risk_gate_halts_when_freshness_snapshot_is_malformed(settings) -> None:
    run_migrations_to_head(settings)
    trace_id = _seed_policy_trace(
        settings,
        run_id="risk_malformed_snapshot",
        semantic_regime="long_friendly",
        freshness_snapshot_json="{not-valid-json",
    )

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)

    assert result["allowed"] is False
    assert result["risk_state"] == "halted"
    assert result["halted"] is True
    assert result["reason_codes"] == ["freshness_snapshot_malformed"]


def test_risk_gate_halts_when_required_lane_is_not_downstream_eligible(settings) -> None:
    run_migrations_to_head(settings)
    trace_id = _seed_policy_trace(
        settings,
        run_id="risk_stale_required_lane",
        semantic_regime="short_friendly",
        freshness_snapshot_json=json.dumps(
            _freshness_snapshot(
                lane_overrides={
                    "coinbase-candles": {
                        "downstream_eligible": False,
                        "freshness_state": "stale",
                    }
                }
            )
        ),
    )

    result = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)

    assert result["allowed"] is False
    assert result["risk_state"] == "halted"
    assert result["halted"] is True
    assert "required_lane_downstream_ineligible:coinbase-candles" in result["reason_codes"]

    session = get_session(settings)
    try:
        verdict = session.query(RiskGlobalRegimeGateV1).one()
        trace = session.query(PolicyGlobalRegimeTraceV1).one()
    finally:
        session.close()

    assert verdict.policy_trace_id == trace.id
    assert verdict.policy_state == "eligible_short"
    assert verdict.risk_state == "halted"
    assert verdict.stale_data_authorized_flag == 0
    assert verdict.unresolved_input_flag == 0
