from __future__ import annotations

from datetime import timedelta

import orjson

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.runtime.diagnostics import (
    diagnose_gate_funnel,
    diagnose_no_trades,
    diagnose_training_window,
)
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    FeatureGlobalRegimeInput15mV1,
    FeatureMaterializationRun,
    IngestRun,
    MarketCandle,
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
    PaperPracticeProfileRevisionV1,
    PaperPracticeProfileV1,
)


def _seed_paper_loop_with_decisions(settings) -> None:
    now = utcnow()
    session = get_session(settings)
    try:
        profile = PaperPracticeProfileV1(
            profile_id="paper_diag_profile",
            status="active",
            active_revision_id=None,
            instrument_pair="SOL/USDC",
            context_anchors_json="[]",
            cadence_minutes=15,
            max_open_sessions=1,
            created_at=now,
            updated_at=now,
        )
        session.add(profile)
        session.flush()
        session.add(
            PaperPracticeProfileRevisionV1(
                revision_id="paper_diag_revision",
                profile_id="paper_diag_profile",
                revision_index=1,
                status="active",
                mutation_source="bootstrap",
                applied_parameter_json="{}",
                allowed_mutation_keys_json="[]",
                summary="diagnostic test revision",
                created_at=now,
            )
        )
        session.flush()
        profile.active_revision_id = "paper_diag_revision"
        session.add(
            PaperPracticeLoopRunV1(
                loop_run_id="paper_diag_loop",
                mode="bounded",
                status="completed",
                active_profile_id="paper_diag_profile",
                active_revision_id="paper_diag_revision",
                with_helius_ws=0,
                max_iterations=3,
                iterations_completed=3,
                latest_decision_id="diag_trade_opened",
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.flush()
        session.add_all(
            [
                PaperPracticeDecisionV1(
                    decision_id="diag_strategy_mismatch",
                    loop_run_id="paper_diag_loop",
                    profile_id="paper_diag_profile",
                    profile_revision_id="paper_diag_revision",
                    decision_type="no_trade",
                    condition_run_id="condition_diag",
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(
                        [
                            "strategy_target_not_runtime_long:flat",
                            "strategy_regime_not_allowed:long_friendly",
                        ]
                    ).decode(),
                    created_at=now,
                ),
                PaperPracticeDecisionV1(
                    decision_id="diag_condition_block",
                    loop_run_id="paper_diag_loop",
                    profile_id="paper_diag_profile",
                    profile_revision_id="paper_diag_revision",
                    decision_type="no_trade",
                    condition_run_id="condition_diag",
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(
                        ["condition_confidence_below_profile_minimum"]
                    ).decode(),
                    created_at=now + timedelta(minutes=15),
                ),
                PaperPracticeDecisionV1(
                    decision_id="diag_trade_opened",
                    loop_run_id="paper_diag_loop",
                    profile_id="paper_diag_profile",
                    profile_revision_id="paper_diag_revision",
                    decision_type="paper_trade_opened",
                    condition_run_id="condition_diag",
                    policy_trace_id=1,
                    risk_verdict_id=1,
                    decision_payload_json=orjson.dumps({}).decode(),
                    reason_codes_json=orjson.dumps(["paper_trade_opened"]).decode(),
                    created_at=now + timedelta(minutes=30),
                ),
            ]
        )
        session.commit()
    finally:
        session.close()


def _seed_training_window(settings) -> None:
    now = utcnow()
    session = get_session(settings)
    try:
        session.add(
            IngestRun(
                run_id="diag_market_ingest",
                provider="coinbase",
                capture_type="candles",
                status="completed",
                started_at=now,
                finished_at=now,
                records_captured=3,
                created_at=now,
            )
        )
        session.flush()
        session.add(
            FeatureMaterializationRun(
                run_id="diag_feature_run",
                feature_set="global_regime_inputs_15m_v1",
                source_tables="market_candle",
                input_window_start_utc=now - timedelta(days=2),
                input_window_end_utc=now,
                row_count=2,
                status="completed",
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.flush()
        for offset in range(3):
            ts = now - timedelta(days=offset)
            session.add(
                MarketCandle(
                    ingest_run_id="diag_market_ingest",
                    venue="coinbase",
                    product_id="SOL-USD",
                    granularity="ONE_MINUTE",
                    start_time_utc=ts,
                    end_time_utc=ts + timedelta(minutes=1),
                    open=100.0 + offset,
                    high=101.0 + offset,
                    low=99.0 + offset,
                    close=100.5 + offset,
                    volume=10.0,
                    source_event_time_utc=ts,
                    captured_at_utc=ts,
                    source_time_raw=ts.isoformat(),
                    event_date_utc=ts.strftime("%Y-%m-%d"),
                    hour_utc=ts.hour,
                    minute_of_day_utc=(ts.hour * 60) + ts.minute,
                    weekday_utc=ts.weekday(),
                    time_quality="source",
                )
            )
        for offset in range(2):
            ts = now - timedelta(days=offset)
            session.add(
                FeatureGlobalRegimeInput15mV1(
                    feature_run_id="diag_feature_run",
                    bucket_start_utc=ts,
                    regime_key="global",
                    proxy_products_json='["SOL-USD"]',
                    proxy_count=1,
                    market_return_mean_15m=0.01,
                    market_return_std_15m=0.02,
                    market_realized_vol_15m=0.03,
                    market_volume_sum_15m=100.0,
                    market_trade_count_15m=10,
                    market_trade_size_sum_15m=20.0,
                    market_book_spread_bps_mean_15m=5.0,
                    event_date_utc=ts.strftime("%Y-%m-%d"),
                    hour_utc=ts.hour,
                    minute_of_day_utc=(ts.hour * 60) + ts.minute,
                    weekday_utc=ts.weekday(),
                    created_at=now,
                )
            )
        session.commit()
    finally:
        session.close()


def test_diagnose_no_trades_identifies_primary_failure_surface(settings) -> None:
    run_migrations_to_head(settings)
    _seed_paper_loop_with_decisions(settings)

    result = diagnose_no_trades(settings, run="latest", window="300d")

    assert result["total_decision_cycles"] == 3
    assert result["no_trade_cycles"] == 2
    assert result["paper_trades"] == 1
    assert result["primary_failure_surface"] == "strategy_candidate_generation"
    assert {
        item["reason_code"] for item in result["top_reason_codes"]
    } >= {"strategy_target_not_runtime_long:flat", "paper_trade_opened"}
    assert "baseline candidate strategy" in result["recommended_next_action"]
    assert (settings.repo_root / ".ai" / "dropbox" / "state" / "diagnose_no_trades_latest.json").exists()


def test_diagnose_gate_funnel_counts_stages(settings) -> None:
    run_migrations_to_head(settings)
    _seed_paper_loop_with_decisions(settings)

    result = diagnose_gate_funnel(settings, run="latest")

    assert result["cycles"] == 3
    assert result["valid_conditions"] == 3
    assert result["policy_allowed"] == 1
    assert result["risk_approved"] == 1
    assert result["paper_filled"] == 1
    assert result["no_trade_cycles"] == 2
    assert result["primary_failure_surface"] == "strategy_candidate_generation"


def test_diagnose_training_window_reports_sql_and_feature_coverage(settings) -> None:
    run_migrations_to_head(settings)
    _seed_training_window(settings)

    result = diagnose_training_window(settings, regimen="quickstart_300d")

    assert result["regimen"] == "quickstart_300d"
    assert result["expected_days"] == 300
    assert result["sql_days_present"] == 3
    assert result["feature_days_present"] == 2
    assert result["status"] == "degraded"
    assert result["primary_failure_surface"] == "data"
    assert result["missing_day_count"] == 297
    assert result["summary_path"].endswith("summary.json")
