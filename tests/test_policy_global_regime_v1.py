from __future__ import annotations

import json
from datetime import timedelta

import pytest

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.policy.global_regime_v1 import GlobalRegimePolicyEvaluator
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    FeatureMaterializationRun,
    PolicyGlobalRegimeTraceV1,
)


def _seed_condition_receipt(
    settings,
    *,
    run_id: str,
    semantic_regime: str,
    blocked_flag: int = 0,
    blocking_reason: str | None = None,
    status: str = "success",
    confidence: float | None = 0.81,
    error_message: str | None = None,
    started_at=None,
    finished_at=None,
):
    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    started_at = started_at or (now - timedelta(minutes=10))
    finished_at = finished_at or (started_at + timedelta(minutes=1))
    feature_run_id = f"feature_{run_id}"
    try:
        session.add(
            FeatureMaterializationRun(
                run_id=feature_run_id,
                feature_set="global_regime_inputs_15m_v1",
                source_tables="[]",
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
                status=status,
                confidence=confidence,
                error_message=error_message,
                started_at=started_at,
                finished_at=finished_at,
                created_at=started_at,
            )
        )
        session.flush()

        snapshot = None
        if status == "success":
            snapshot = ConditionGlobalRegimeSnapshotV1(
                condition_run_id=run_id,
                source_feature_run_id=feature_run_id,
                bucket_start_utc=started_at - timedelta(minutes=15),
                raw_state_id=1,
                semantic_regime=semantic_regime,
                confidence=float(confidence or 0.0),
                blocked_flag=blocked_flag,
                blocking_reason=blocking_reason,
                model_family="gaussian_hmm_4state",
                macro_context_state="healthy_recent",
                created_at=finished_at,
            )
            session.add(snapshot)
            session.flush()

        session.commit()
        return feature_run_id, snapshot.id if snapshot is not None else None
    finally:
        session.close()


def test_policy_evaluator_emits_eligible_long_and_persists_trace(settings) -> None:
    run_migrations_to_head(settings)
    feature_run_id, snapshot_id = _seed_condition_receipt(
        settings,
        run_id="condition_long_policy",
        semantic_regime="long_friendly",
    )

    result = GlobalRegimePolicyEvaluator(settings).evaluate()

    assert result["policy_state"] == "eligible_long"
    assert "yaml_allows_new_long_hypotheses" in result["reason_codes"]

    session = get_session(settings)
    try:
        trace = session.query(PolicyGlobalRegimeTraceV1).one()
    finally:
        session.close()

    assert trace.condition_snapshot_id == snapshot_id
    assert trace.source_feature_run_id == feature_run_id
    assert trace.policy_state == "eligible_long"
    assert trace.allow_new_long_hypotheses == 1
    assert trace.allow_new_short_hypotheses == 0
    assert len(trace.config_hash) == 64
    assert trace.config_version == 1
    assert trace.config_status == "runtime_policy_input"
    assert json.loads(trace.reason_codes_json) == result["reason_codes"]


def test_policy_evaluator_emits_eligible_short(settings) -> None:
    run_migrations_to_head(settings)
    _seed_condition_receipt(
        settings,
        run_id="condition_short_policy",
        semantic_regime="short_friendly",
    )

    result = GlobalRegimePolicyEvaluator(settings).evaluate()

    assert result["policy_state"] == "eligible_short"
    assert "yaml_allows_new_short_hypotheses" in result["reason_codes"]


@pytest.mark.parametrize("semantic_regime", ["risk_off", "no_trade"])
def test_policy_evaluator_forces_no_trade_for_fail_closed_regimes(
    settings,
    semantic_regime: str,
) -> None:
    run_migrations_to_head(settings)
    _seed_condition_receipt(
        settings,
        run_id=f"condition_{semantic_regime}",
        semantic_regime=semantic_regime,
    )

    result = GlobalRegimePolicyEvaluator(settings).evaluate()

    assert result["policy_state"] == "no_trade"
    assert "semantic_regime_forces_no_trade" in result["reason_codes"]


def test_policy_evaluator_forces_no_trade_when_condition_is_blocked(settings) -> None:
    run_migrations_to_head(settings)
    _seed_condition_receipt(
        settings,
        run_id="condition_blocked_policy",
        semantic_regime="long_friendly",
        blocked_flag=1,
        blocking_reason="risk_off",
    )

    result = GlobalRegimePolicyEvaluator(settings).evaluate()

    assert result["policy_state"] == "no_trade"
    assert "condition_blocked" in result["reason_codes"]


def test_policy_evaluator_fails_closed_on_latest_failed_condition_run(settings) -> None:
    run_migrations_to_head(settings)
    now = utcnow().replace(second=0, microsecond=0)
    _seed_condition_receipt(
        settings,
        run_id="condition_old_success",
        semantic_regime="long_friendly",
        started_at=now - timedelta(minutes=40),
        finished_at=now - timedelta(minutes=39),
    )
    _seed_condition_receipt(
        settings,
        run_id="condition_latest_failed",
        semantic_regime="long_friendly",
        status="failed",
        confidence=None,
        error_message="freshness authorization failed",
        started_at=now - timedelta(minutes=5),
        finished_at=now - timedelta(minutes=4),
    )

    with pytest.raises(RuntimeError, match="Latest condition run is not successful"):
        GlobalRegimePolicyEvaluator(settings).evaluate()

    session = get_session(settings)
    try:
        trace_count = session.query(PolicyGlobalRegimeTraceV1).count()
    finally:
        session.close()

    assert trace_count == 0


def test_policy_evaluator_fails_closed_on_invalid_yaml(settings, monkeypatch, tmp_path) -> None:
    run_migrations_to_head(settings)
    _seed_condition_receipt(
        settings,
        run_id="condition_invalid_yaml",
        semantic_regime="long_friendly",
    )
    bad_policy_path = tmp_path / "broken_policy.yaml"
    bad_policy_path.write_text("version: [broken", encoding="utf-8")

    import d5_trading_engine.policy.global_regime_v1 as policy_module

    monkeypatch.setattr(policy_module, "GLOBAL_REGIME_V1_BIAS_MAP", bad_policy_path)

    with pytest.raises(RuntimeError, match="Policy config is invalid"):
        GlobalRegimePolicyEvaluator(settings).evaluate()
