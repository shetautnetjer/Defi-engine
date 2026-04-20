from __future__ import annotations

import csv
import json
import math
from datetime import timedelta
from pathlib import Path

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.features.materializer import _GLOBAL_REGIME_FEATURE_SET_NAME
from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    BacktestSessionV1,
    FeatureGlobalRegimeInput15mV1,
    FeatureMaterializationRun,
    ImprovementProposalV1,
    IngestRun,
    MarketCandle,
)
from tests.test_backtest_truth import _seed_tracked_tokens


def _seed_strategy_report(settings) -> None:
    report_path = (
        settings.repo_root
        / ".ai"
        / "dropbox"
        / "research"
        / "STRAT-001__strategy_challenger_report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "run_id": "strategy_eval_test",
                "generated_at": utcnow().isoformat(),
                "auto_promotion_eligible": False,
                "top_family": "trend_continuation_long_v1",
                "families": {
                    "trend_continuation_long_v1": {
                        "eligible": True,
                        "positive_expectancy": 0.18,
                        "xgb_accuracy": 0.64,
                        "xgb_auc": 0.67,
                    },
                    "flat_regime_stand_aside_v1": {
                        "eligible": True,
                        "positive_expectancy": 0.05,
                        "xgb_accuracy": 0.58,
                        "xgb_auc": 0.59,
                    },
                },
            }
        ),
        encoding="utf-8",
    )


def _seed_walk_forward_history(settings) -> None:
    session = get_session(settings)
    now = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    feature_run_id = "feature_walk_forward_test"
    start = now - timedelta(days=540)
    try:
        session.add(
            FeatureMaterializationRun(
                run_id=feature_run_id,
                feature_set=_GLOBAL_REGIME_FEATURE_SET_NAME,
                status="success",
                row_count=540,
                started_at=now,
                finished_at=now,
                freshness_snapshot_json=json.dumps(
                    {
                        "required_lanes": {
                            "fred-observations": {
                                "freshness_state": "healthy_recent",
                            }
                        }
                    }
                ),
                created_at=now,
            )
        )
        session.add(
            IngestRun(
                run_id="massive_backtest_walk_forward",
                provider="massive",
                capture_type="minute_aggs",
                status="success",
                started_at=now,
                finished_at=now,
                records_captured=540,
                created_at=now,
            )
        )
        session.commit()
        for day_offset in range(540):
            bucket = start + timedelta(days=day_offset)
            phase = day_offset // 90
            direction = 1 if phase % 2 == 0 else -1
            market_return = direction * (0.0015 + (math.sin(day_offset / 8.0) * 0.0002))
            base_price = 100.0 + (day_offset * 0.08 * direction)
            close_price = max(10.0, base_price + (direction * 0.6))
            session.add(
                FeatureGlobalRegimeInput15mV1(
                    feature_run_id=feature_run_id,
                    bucket_start_utc=bucket,
                    regime_key="global",
                    proxy_products_json=json.dumps(["X:SOLUSD", "X:BTCUSD", "X:ETHUSD"]),
                    proxy_count=3,
                    market_return_mean_15m=market_return,
                    market_return_std_15m=abs(market_return) * 0.35,
                    market_realized_vol_15m=0.02 + (0.01 * phase),
                    market_volume_sum_15m=1000.0 + (phase * 100.0),
                    market_trade_count_15m=25 + phase,
                    market_trade_size_sum_15m=250.0 + (phase * 25.0),
                    market_book_spread_bps_mean_15m=4.0 + phase,
                    market_return_mean_4h=market_return * 4.0,
                    market_realized_vol_4h=0.05 + (phase * 0.015),
                    macro_context_available=1,
                    fred_dff=4.25,
                    fred_t10y2y=-0.25,
                    fred_vixcls=18.0 + phase,
                    fred_dgs10=4.1,
                    fred_dtwexbgs=121.0,
                    event_date_utc=bucket.strftime("%Y-%m-%d"),
                    hour_utc=bucket.hour,
                    minute_of_day_utc=(bucket.hour * 60) + bucket.minute,
                    weekday_utc=bucket.weekday(),
                    created_at=now,
                )
            )
            session.add(
                MarketCandle(
                    ingest_run_id="massive_backtest_walk_forward",
                    venue="massive",
                    product_id="X:SOLUSD",
                    granularity="ONE_MINUTE",
                    start_time_utc=bucket,
                    end_time_utc=None,
                    open=max(10.0, close_price - 0.5),
                    high=close_price + 0.75,
                    low=max(1.0, close_price - 0.75),
                    close=close_price,
                    volume=125.0 + phase,
                    source_event_time_utc=bucket,
                    captured_at_utc=bucket,
                    source_time_raw=bucket.isoformat(),
                    event_date_utc=bucket.strftime("%Y-%m-%d"),
                    hour_utc=bucket.hour,
                    minute_of_day_utc=(bucket.hour * 60) + bucket.minute,
                    weekday_utc=bucket.weekday(),
                    time_quality="source",
                )
            )
        session.commit()
    finally:
        session.close()


def _install_stub_walk_forward_scoring(settings, monkeypatch) -> None:
    def _fake_walk_forward_history(self, history, *, macro_context_state):
        scored = history.copy()
        scored["raw_state_id"] = scored["market_return_mean_15m"].apply(
            lambda value: 0 if value >= 0 else 1
        )
        scored["confidence"] = scored["market_return_mean_15m"].apply(
            lambda value: 0.82 if value >= 0 else 0.78
        )
        scored["semantic_regime"] = scored["market_return_mean_15m"].apply(
            lambda value: "long_friendly" if value >= 0 else "risk_off"
        )
        scored["model_family"] = "stub_hmm"
        scored["model_epoch_bucket_start_utc"] = scored["bucket_start_utc"]
        scored["training_window_start_utc"] = scored["bucket_start_utc"]
        scored["training_window_end_utc"] = scored["bucket_start_utc"]
        return (
            scored,
            {
                0: {"semantic_regime": "long_friendly"},
                1: {"semantic_regime": "risk_off"},
            },
            "stub_hmm",
        )

    monkeypatch.setattr(
        "d5_trading_engine.condition.scorer.ConditionScorer._build_walk_forward_history_frame",
        _fake_walk_forward_history,
    )
    monkeypatch.setattr(
        "d5_trading_engine.research_loop.regime_model_compare.RegimeModelComparator.run_regime_model_compare_v1",
        lambda self, **kwargs: {
            "run_id": f"comparison_{kwargs.get('history_end', 'window')}",
            "artifact_dir": str(settings.data_dir / "research" / "regime_model_compare" / "test"),
            "recommended_candidate": "hmm",
            "proposal_status": "proposed",
        },
    )
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_ensure_advisory_strategy_report",
        lambda self: {
            "status": "test_stub",
            "strategy_report_path": str(
                settings.repo_root
                / ".ai"
                / "dropbox"
                / "research"
                / "STRAT-001__strategy_challenger_report.json"
            ),
            "strategy_report_exists": True,
            "run_id": "strategy_eval_test",
            "top_family": "test_stub",
            "proposal_status": "proposed",
        },
    )


def test_backtest_walk_forward_replays_windows_and_governor_gates_profile_adaptation(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    _seed_tracked_tokens(settings)
    _seed_strategy_report(settings)
    _seed_walk_forward_history(settings)

    _install_stub_walk_forward_scoring(settings, monkeypatch)
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_load_profile_strategy_selection",
        lambda self, payload: {
            "top_family": "trend_continuation_long_v1",
            "target_label": "up",
            "allowed_regimes": ["long_friendly"],
        },
    )

    runtime = PaperPracticeRuntime(settings)
    runtime.ensure_active_profile()
    result = runtime.run_backtest_walk_forward(training_profile_name="full_730d")

    assert result["status"] == "completed"
    assert result["completed_ladder"] is True
    assert result["window_count"] >= 2

    session = get_session(settings)
    try:
        backtest_sessions = (
            session.query(BacktestSessionV1)
            .order_by(BacktestSessionV1.session_key.asc())
            .all()
        )
        proposals = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_kind="paper_profile_adjustment_follow_on")
            .all()
        )
    finally:
        session.close()

    assert len(backtest_sessions) == result["window_count"]
    assert all(row.status == "closed" for row in backtest_sessions)
    assert proposals
    assert result["active_revision_id"] == result["starting_revision_id"]
    assert result["window_results"][0]["proposal_applied"] is False


def test_backtest_walk_forward_writes_replay_audit_for_missed_long_entries(
    settings,
    monkeypatch,
) -> None:
    run_migrations_to_head(settings)
    _seed_tracked_tokens(settings)
    _seed_strategy_report(settings)
    _seed_walk_forward_history(settings)
    _install_stub_walk_forward_scoring(settings, monkeypatch)
    monkeypatch.setattr(
        PaperPracticeRuntime,
        "_load_profile_strategy_selection",
        lambda self, payload: {
            "top_family": "flat_regime_stand_aside_v1",
            "target_label": "flat",
            "allowed_regimes": ["no_trade", "risk_off"],
        },
    )

    runtime = PaperPracticeRuntime(settings)
    runtime.ensure_active_profile()
    result = runtime.run_backtest_walk_forward(training_profile_name="full_730d")

    first_window = result["window_results"][0]
    audit_summary = first_window["replay_audit_summary"]
    audit_csv_path = Path(first_window["replay_audit_csv_path"])

    assert audit_summary["row_count"] > 0
    assert audit_summary["market_return_direction_counts"]["up"] > 0
    assert audit_summary["semantic_regime_counts"]["long_friendly"] > 0
    assert audit_summary["would_open_runtime_long_count"] == 0
    assert (
        audit_summary["blocked_reason_counts"]["strategy_target_not_runtime_long:flat"]
        == audit_summary["row_count"]
    )
    assert audit_csv_path.exists()

    with audit_csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert {
        "bucket_start_utc",
        "close_price_usdc",
        "market_return_mean_15m",
        "market_return_direction",
        "semantic_regime",
        "confidence",
        "strategy_target_label",
        "strategy_allowed_regimes",
        "profile_regime_allowed",
        "strategy_runtime_long_supported",
        "strategy_regime_allowed",
        "would_open_runtime_long",
        "no_trade_reason_codes",
    }.issubset(rows[0])
    assert any(row["market_return_direction"] == "up" for row in rows)
    assert all(row["would_open_runtime_long"] == "false" for row in rows)
    assert any(
        "strategy_target_not_runtime_long:flat" in row["no_trade_reason_codes"]
        for row in rows
    )
