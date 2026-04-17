from __future__ import annotations

import json
import math
from datetime import timedelta

import pandas.testing as pdt

from d5_trading_engine.cli import cli
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.condition.scorer import ConditionScorer
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    FeatureGlobalRegimeInput15mV1,
    FeatureMaterializationRun,
    FredObservation,
    FredSeriesRegistry,
    IngestRun,
    MarketCandle,
    MarketInstrumentRegistry,
    MarketTradeEvent,
    OrderBookL2Event,
    SourceHealthEvent,
)


def _seed_global_regime_inputs(
    settings,
    *,
    include_macro_health: bool = True,
    total_15m_buckets: int = 96,
    anchor_now=None,
    same_day_fred_captured_at=None,
) -> None:
    session = get_session(settings)
    now = anchor_now or utcnow().replace(second=0, microsecond=0)
    minute_start = now - timedelta(minutes=total_15m_buckets * 15)
    products = {
        "BTC-USD": {"base": "BTC", "price": 64000.0, "offset": 0.1},
        "ETH-USD": {"base": "ETH", "price": 3200.0, "offset": 0.7},
        "SOL-USD": {"base": "SOL", "price": 140.0, "offset": 1.3},
    }
    try:
        for run_id, provider, capture_type in (
            ("coinbase_products_run_100", "coinbase", "products"),
            ("coinbase_candles_run_100", "coinbase", "candles"),
            ("coinbase_trades_run_100", "coinbase", "market_trades"),
            ("coinbase_book_run_100", "coinbase", "book"),
            ("fred_run_100", "fred", "observations"),
        ):
            session.add(
                IngestRun(
                    run_id=run_id,
                    provider=provider,
                    capture_type=capture_type,
                    status="success",
                    started_at=now,
                    finished_at=now,
                    records_captured=1,
                    created_at=now,
                )
            )
        session.flush()

        for endpoint in (
            "/market/products",
            "/market/products/*/candles",
            "/market/products/*/ticker",
            "/market/product_book",
        ):
            session.add(
                SourceHealthEvent(
                    provider="coinbase",
                    endpoint=endpoint,
                    status_code=200,
                    latency_ms=120.0,
                    is_healthy=1,
                    error_message=None,
                    checked_at=now,
                )
            )
        if include_macro_health:
            session.add(
                SourceHealthEvent(
                    provider="fred",
                    endpoint="observations",
                    status_code=200,
                    latency_ms=210.0,
                    is_healthy=1,
                    error_message=None,
                    checked_at=now,
                )
            )

        for product_id, config in products.items():
            session.add(
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id=product_id,
                    base_symbol=config["base"],
                    quote_symbol="USD",
                    product_type="SPOT",
                    status="online",
                    price_increment="0.01",
                    base_increment="0.00000001",
                    quote_increment="0.01",
                    first_seen_at=now,
                    updated_at=now,
                )
            )

        prices = {product_id: config["price"] for product_id, config in products.items()}
        total_minutes = total_15m_buckets * 15
        for minute_index in range(total_minutes):
            ts = minute_start + timedelta(minutes=minute_index)
            phase_size = total_minutes // 4
            phase = min(3, minute_index // phase_size)
            phase_drift = [0.0005, -0.0009, 0.00005, 0.00035][phase]
            phase_vol = [0.0004, 0.0014, 0.00025, 0.0009][phase]
            for product_id, config in products.items():
                prev_price = prices[product_id]
                signal = math.sin((minute_index / 9.0) + config["offset"])
                step_return = phase_drift + (phase_vol * signal)
                close_price = max(1.0, prev_price * (1.0 + step_return))
                high_price = max(prev_price, close_price) * (1.0 + abs(step_return) * 0.35)
                low_price = min(prev_price, close_price) * (1.0 - abs(step_return) * 0.35)
                volume = 8.0 + phase + abs(signal) * 3.0

                session.add(
                    MarketCandle(
                        ingest_run_id="coinbase_candles_run_100",
                        venue="coinbase",
                        product_id=product_id,
                        granularity="ONE_MINUTE",
                        start_time_utc=ts,
                        end_time_utc=None,
                        open=prev_price,
                        high=high_price,
                        low=low_price,
                        close=close_price,
                        volume=volume,
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
                session.add(
                    MarketTradeEvent(
                        ingest_run_id="coinbase_trades_run_100",
                        venue="coinbase",
                        product_id=product_id,
                        trade_id=f"{product_id}-{minute_index}",
                        side="buy" if step_return >= 0 else "sell",
                        price=close_price,
                        size=volume / 10.0,
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
                session.add(
                    OrderBookL2Event(
                        ingest_run_id="coinbase_book_run_100",
                        venue="coinbase",
                        product_id=product_id,
                        event_kind="snapshot",
                        best_bid=close_price * 0.999,
                        best_ask=close_price * 1.001,
                        spread_absolute=close_price * 0.002,
                        spread_bps=5.0 + (phase * 2.5) + abs(signal),
                        bids_json="[]",
                        asks_json="[]",
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
                prices[product_id] = close_price

        for offset_days, value_map in (
            (1, {"DFF": 4.25, "T10Y2Y": -0.35, "VIXCLS": 17.2, "DGS10": 4.12, "DTWEXBGS": 121.0}),
            (0, {"DFF": 4.33, "T10Y2Y": -0.28, "VIXCLS": 18.4, "DGS10": 4.18, "DTWEXBGS": 121.7}),
        ):
            obs_date = (now - timedelta(days=offset_days)).strftime("%Y-%m-%d")
            captured_at = (
                now - timedelta(days=1)
                if offset_days == 1
                else (same_day_fred_captured_at or now)
            )
            for series_id, value in value_map.items():
                if offset_days == 1:
                    session.add(
                        FredSeriesRegistry(
                            series_id=series_id,
                            title=series_id,
                            frequency="Daily",
                            units="Index",
                            seasonal_adjustment=None,
                            last_updated=now,
                            provider="fred",
                            first_seen_at=now,
                            updated_at=now,
                        )
                    )
                session.add(
                    FredObservation(
                        ingest_run_id="fred_run_100",
                        series_id=series_id,
                        observation_date=obs_date,
                        value=value,
                        realtime_start=obs_date,
                        realtime_end=obs_date,
                        provider="fred",
                        captured_at=captured_at,
                    )
                )

        session.commit()
    finally:
        session.close()


def test_cli_materializes_and_scores_global_regime(cli_runner, settings) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _seed_global_regime_inputs(settings)

    materialize_result = cli_runner.invoke(
        cli,
        ["materialize-features", "global-regime-inputs-15m-v1"],
    )
    assert materialize_result.exit_code == 0
    assert "global_regime_inputs_15m_v1" in materialize_result.output

    score_result = cli_runner.invoke(cli, ["score-conditions", "global-regime-v1"])
    assert score_result.exit_code == 0
    assert "global_regime_v1" in score_result.output

    session = get_session(settings)
    try:
        feature_run = (
            session.query(FeatureMaterializationRun)
            .filter_by(feature_set="global_regime_inputs_15m_v1")
            .one()
        )
        feature_rows = (
            session.query(FeatureGlobalRegimeInput15mV1)
            .filter_by(feature_run_id=feature_run.run_id)
            .count()
        )
        condition_run = session.query(ConditionScoringRun).one()
        snapshot = session.query(ConditionGlobalRegimeSnapshotV1).one()
    finally:
        session.close()

    freshness_snapshot = json.loads(feature_run.freshness_snapshot_json or "{}")

    assert feature_run.status == "success"
    assert feature_rows >= 40
    assert (
        freshness_snapshot["required_lanes"]["coinbase-candles"]["freshness_state"]
        == "healthy_recent"
    )
    assert condition_run.status == "success"
    assert condition_run.source_feature_run_id == feature_run.run_id
    assert snapshot.semantic_regime in {
        "long_friendly",
        "short_friendly",
        "risk_off",
        "no_trade",
    }
    assert 0.0 <= snapshot.confidence <= 1.0
    assert snapshot.model_family in {
        "gaussian_hmm_4state",
        "gaussian_mixture_regime_proxy_4state",
    }


def test_global_regime_materialization_allows_degraded_macro_lane(cli_runner, settings) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _seed_global_regime_inputs(settings, include_macro_health=False)

    materialize_result = cli_runner.invoke(
        cli,
        ["materialize-features", "global-regime-inputs-15m-v1"],
    )
    assert materialize_result.exit_code == 0

    score_result = cli_runner.invoke(cli, ["score-conditions", "global-regime-v1"])
    assert score_result.exit_code == 0

    session = get_session(settings)
    try:
        feature_run = (
            session.query(FeatureMaterializationRun)
            .filter_by(feature_set="global_regime_inputs_15m_v1")
            .one()
        )
        snapshot = session.query(ConditionGlobalRegimeSnapshotV1).one()
    finally:
        session.close()

    freshness_snapshot = json.loads(feature_run.freshness_snapshot_json or "{}")

    assert (
        freshness_snapshot["required_lanes"]["fred-observations"]["required_for_authorization"]
        is False
    )
    assert (
        freshness_snapshot["required_lanes"]["fred-observations"]["freshness_state"]
        == "degraded"
    )
    assert snapshot.macro_context_state == "degraded"


def test_walk_forward_regime_history_is_point_in_time_safe(cli_runner, settings) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _seed_global_regime_inputs(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )

    scorer = ConditionScorer(settings)
    session = get_session(settings)
    try:
        feature_run = (
            session.query(FeatureMaterializationRun)
            .filter_by(feature_set="global_regime_inputs_15m_v1")
            .one()
        )
    finally:
        session.close()

    full_history = scorer._load_feature_history(feature_run.run_id)
    truncated_history = full_history.iloc[:80].copy()
    truncated_scored, _, _ = scorer._build_walk_forward_history_frame(
        truncated_history,
        macro_context_state="healthy_recent",
    )
    full_scored, _, _ = scorer._build_walk_forward_history_frame(
        full_history,
        macro_context_state="healthy_recent",
    )

    overlap = full_scored.loc[
        full_scored["bucket_start_utc"].isin(truncated_scored["bucket_start_utc"])
    ].reset_index(drop=True)
    columns = [
        "bucket_start_utc",
        "raw_state_id",
        "semantic_regime",
        "model_family",
        "model_epoch_bucket_start_utc",
        "training_window_start_utc",
        "training_window_end_utc",
    ]
    pdt.assert_frame_equal(
        overlap[columns],
        truncated_scored[columns].reset_index(drop=True),
    )
    assert overlap["confidence"].round(10).tolist() == truncated_scored[
        "confidence"
    ].round(10).tolist()


def test_walk_forward_regime_history_refits_every_four_buckets(cli_runner, settings) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _seed_global_regime_inputs(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )

    history = ConditionScorer(settings).build_walk_forward_regime_history().history
    epoch_counts = history.groupby("model_epoch_bucket_start_utc").size().tolist()

    assert epoch_counts
    assert all(count == 4 for count in epoch_counts[:-1])
    assert 1 <= epoch_counts[-1] <= 4


def test_global_regime_materialization_respects_fred_captured_at(cli_runner, settings) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    anchor_now = utcnow().replace(second=0, microsecond=0)
    _seed_global_regime_inputs(
        settings,
        anchor_now=anchor_now,
        same_day_fred_captured_at=anchor_now,
    )

    materialize_result = cli_runner.invoke(
        cli,
        ["materialize-features", "global-regime-inputs-15m-v1"],
    )
    assert materialize_result.exit_code == 0

    session = get_session(settings)
    try:
        same_day_rows = (
            session.query(FeatureGlobalRegimeInput15mV1)
            .filter_by(event_date_utc=anchor_now.strftime("%Y-%m-%d"))
            .order_by(FeatureGlobalRegimeInput15mV1.bucket_start_utc.asc())
            .all()
        )
    finally:
        session.close()

    assert same_day_rows
    assert same_day_rows[0].fred_dff == 4.25
    assert same_day_rows[-1].fred_dff == 4.33
