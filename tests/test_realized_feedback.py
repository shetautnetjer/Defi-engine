from __future__ import annotations

import json
from datetime import timedelta

from d5_trading_engine.common.time_utils import ensure_utc
from d5_trading_engine.execution_intent.owner import ExecutionIntentOwner
from d5_trading_engine.features.materializer import FeatureMaterializer
from d5_trading_engine.policy.global_regime_v1 import GlobalRegimePolicyEvaluator
from d5_trading_engine.research_loop.shadow_runner import ShadowRunner
from d5_trading_engine.risk.gate import RiskGate
from d5_trading_engine.settlement.paper import PaperSettlement
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    ExperimentMetric,
    ExperimentRealizedFeedbackV1,
    FeatureGlobalRegimeInput15mV1,
    FeatureMaterializationRun,
    FeatureSpotChainMacroMinuteV1,
    TokenRegistry,
)
from tests.test_settlement_paper import _seed_quote_snapshot
from tests.test_shadow_runner import _FakeChronosPipeline, _prepare_shadow_runtime


def _floor_to_bucket(ts, minutes: int):
    return ts - timedelta(
        minutes=ts.minute % minutes,
        seconds=ts.second,
        microseconds=ts.microsecond,
    )


def _seed_shadow_aligned_paper_fill(settings, *, no_shadow_row: bool = False) -> int:
    session = get_session(settings)
    try:
        regime_feature_run = (
            session.query(FeatureMaterializationRun)
            .filter_by(feature_set="global_regime_inputs_15m_v1", status="success")
            .order_by(FeatureMaterializationRun.finished_at.desc())
            .first()
        )
        assert regime_feature_run is not None

        regime_row = (
            session.query(FeatureGlobalRegimeInput15mV1)
            .filter_by(feature_run_id=regime_feature_run.run_id)
            .order_by(FeatureGlobalRegimeInput15mV1.bucket_start_utc.desc())
            .first()
        )
        spot_row = (
            session.query(FeatureSpotChainMacroMinuteV1)
            .order_by(FeatureSpotChainMacroMinuteV1.feature_minute_utc.desc())
            .first()
        )
        assert regime_row is not None
        assert spot_row is not None
        usdc_mint = next(
            mint
            for mint, symbol in settings.token_symbol_hints.items()
            if symbol == "USDC"
        )
        (
            session.query(TokenRegistry)
            .filter(TokenRegistry.mint.in_([usdc_mint, spot_row.mint]))
            .delete(synchronize_session=False)
        )

        bucket_start = regime_row.bucket_start_utc
        aligned_attempted_at = spot_row.feature_minute_utc
        if no_shadow_row:
            aligned_attempted_at = _floor_to_bucket(bucket_start, 15) + timedelta(
                minutes=15,
                seconds=1,
            )

        condition_suffix = "skipped" if no_shadow_row else "matched"
        condition_run_id = f"condition_realized_feedback_{condition_suffix}"
        session.add(
            ConditionScoringRun(
                run_id=condition_run_id,
                condition_set="global_regime_v1",
                source_feature_run_id=regime_feature_run.run_id,
                model_family="gaussian_hmm_4state",
                status="success",
                confidence=0.84,
                started_at=aligned_attempted_at - timedelta(minutes=5),
                finished_at=aligned_attempted_at - timedelta(minutes=4),
                created_at=aligned_attempted_at - timedelta(minutes=5),
            )
        )
        session.flush()
        session.add(
            ConditionGlobalRegimeSnapshotV1(
                condition_run_id=condition_run_id,
                source_feature_run_id=regime_feature_run.run_id,
                bucket_start_utc=bucket_start,
                raw_state_id=1,
                semantic_regime="long_friendly",
                confidence=0.84,
                blocked_flag=0,
                blocking_reason=None,
                model_family="gaussian_hmm_4state",
                macro_context_state="available",
                created_at=aligned_attempted_at - timedelta(minutes=4),
            )
        )
        session.commit()
    finally:
        session.close()

    trace_id = GlobalRegimePolicyEvaluator(settings).evaluate(condition_run_id=condition_run_id)[
        "trace_id"
    ]
    risk_verdict_id = RiskGate(settings).evaluate_global_regime_v1(policy_trace_id=trace_id)[
        "risk_verdict_id"
    ]
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id=f"quote_{condition_run_id}",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=spot_row.mint,
        input_amount="10000000",
        output_amount="100000000",
        captured_at=aligned_attempted_at,
    )
    execution_intent = ExecutionIntentOwner(settings).create_spot_intent(
        risk_verdict_id=risk_verdict_id,
        quote_snapshot_id=quote_snapshot_id,
        intent_created_at=aligned_attempted_at,
    )
    assert execution_intent["ready"] is True
    result = PaperSettlement(settings).simulate_fill(
        execution_intent_id=execution_intent["execution_intent_id"],
        settlement_attempted_at=aligned_attempted_at,
    )
    assert result["filled"] is True
    return result["fill_id"]


def test_shadow_runner_persists_matched_realized_feedback(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    _prepare_shadow_runtime(settings)
    FeatureMaterializer(settings).materialize_global_regime_inputs_15m_v1()
    FeatureMaterializer(settings).materialize_spot_chain_macro_v1()
    fill_id = _seed_shadow_aligned_paper_fill(settings)

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.shadow_runner.ShadowRunner._load_chronos_pipeline",
        lambda self: _FakeChronosPipeline(),
    )

    result = ShadowRunner(settings).run_intraday_meta_stack_v1()

    session = get_session(settings)
    try:
        feedback_rows = (
            session.query(ExperimentRealizedFeedbackV1)
            .filter_by(experiment_run_id=result["run_id"])
            .all()
        )
        metrics = {
            row.metric_name: row.metric_value
            for row in session.query(ExperimentMetric)
            .filter_by(experiment_run_id=result["run_id"])
            .all()
        }
    finally:
        session.close()

    assert len(feedback_rows) == 1
    feedback = feedback_rows[0]
    assert feedback.paper_fill_id == fill_id
    assert feedback.comparison_state == "matched"
    assert feedback.match_method == "feature_run+bucket_15m+mint+merge_asof_backward"
    assert feedback.match_tolerance_seconds == 300

    shadow_context = json.loads(feedback.shadow_context_json)
    realized_outcome = json.loads(feedback.realized_outcome_json)
    reason_codes = json.loads(feedback.reason_codes_json)

    assert shadow_context["matched_mint"] == feedback.matched_mint
    assert shadow_context["matched_bucket_5m_utc"] == ensure_utc(
        feedback.matched_bucket_5m_utc
    ).isoformat()
    assert shadow_context["matched_bucket_15m_utc"] == ensure_utc(
        feedback.matched_bucket_15m_utc
    ).isoformat()
    assert "condition_regime" in shadow_context
    assert reason_codes == []

    assert realized_outcome["fill_side"] == "buy"
    assert realized_outcome["fill_role"] == "entry"
    assert realized_outcome["report_equity_usdc"] is not None
    assert realized_outcome["position_net_quantity"] is not None

    assert metrics["realized_feedback_candidate_fills"] == 1.0
    assert metrics["realized_feedback_matches"] == 1.0
    assert metrics["realized_feedback_skipped"] == 0.0
    assert metrics["realized_feedback_missing_reports"] == 0.0
    assert metrics["realized_feedback_no_shadow_row"] == 0.0


def test_shadow_runner_persists_skipped_realized_feedback_when_shadow_row_missing(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    _prepare_shadow_runtime(settings)
    FeatureMaterializer(settings).materialize_global_regime_inputs_15m_v1()
    FeatureMaterializer(settings).materialize_spot_chain_macro_v1()
    fill_id = _seed_shadow_aligned_paper_fill(settings, no_shadow_row=True)

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.shadow_runner.ShadowRunner._load_chronos_pipeline",
        lambda self: _FakeChronosPipeline(),
    )

    result = ShadowRunner(settings).run_intraday_meta_stack_v1()

    session = get_session(settings)
    try:
        feedback_rows = (
            session.query(ExperimentRealizedFeedbackV1)
            .filter_by(experiment_run_id=result["run_id"])
            .all()
        )
        metrics = {
            row.metric_name: row.metric_value
            for row in session.query(ExperimentMetric)
            .filter_by(experiment_run_id=result["run_id"])
            .all()
        }
    finally:
        session.close()

    assert len(feedback_rows) == 1
    feedback = feedback_rows[0]
    assert feedback.paper_fill_id == fill_id
    assert feedback.comparison_state == "skipped"
    assert feedback.matched_bucket_15m_utc is not None
    assert feedback.matched_bucket_5m_utc is None

    shadow_context = json.loads(feedback.shadow_context_json)
    reason_codes = json.loads(feedback.reason_codes_json)

    assert shadow_context == {}
    assert "no_shadow_row_within_tolerance" in reason_codes

    assert metrics["realized_feedback_candidate_fills"] == 1.0
    assert metrics["realized_feedback_matches"] == 0.0
    assert metrics["realized_feedback_skipped"] == 1.0
    assert metrics["realized_feedback_missing_reports"] == 0.0
    assert metrics["realized_feedback_no_shadow_row"] == 1.0
