from __future__ import annotations

import json
import math
from datetime import timedelta

import pandas.testing as pdt

from d5_trading_engine.cli import cli
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.condition.scorer import ConditionScorer
from d5_trading_engine.features.materializer import FeatureMaterializer
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
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
    receipt_now = utcnow().replace(second=0, microsecond=0)
    minute_start = now - timedelta(minutes=total_15m_buckets * 15)
    products = {
        "BTC-USD": {"base": "BTC", "price": 64000.0, "offset": 0.1},
        "ETH-USD": {"base": "ETH", "price": 3200.0, "offset": 0.7},
        "SOL-USD": {"base": "SOL", "price": 140.0, "offset": 1.3},
    }
    ingest_specs = (
        ("coinbase_products_run_100", "coinbase", "products"),
        ("coinbase_candles_run_100", "coinbase", "candles"),
        ("coinbase_trades_run_100", "coinbase", "market_trades"),
        ("coinbase_book_run_100", "coinbase", "book"),
        ("fred_run_100", "fred", "observations"),
    )
    try:
        existing_runs = {
            run.run_id: run
            for run in session.query(IngestRun)
            .filter(IngestRun.run_id.in_([spec[0] for spec in ingest_specs]))
            .all()
        }
        for run_id, provider, capture_type in ingest_specs:
            existing_run = existing_runs.get(run_id)
            if existing_run is not None:
                existing_run.provider = provider
                existing_run.capture_type = capture_type
                existing_run.status = "success"
                existing_run.started_at = receipt_now
                existing_run.finished_at = receipt_now
                existing_run.records_captured = 1
                existing_run.created_at = receipt_now
                continue
            session.add(
                IngestRun(
                    run_id=run_id,
                    provider=provider,
                    capture_type=capture_type,
                    status="success",
                    started_at=receipt_now,
                    finished_at=receipt_now,
                    records_captured=1,
                    created_at=receipt_now,
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
                    checked_at=receipt_now,
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
                    checked_at=receipt_now,
                )
            )

        existing_coinbase_products = {
            product_id
            for (product_id,) in session.query(MarketInstrumentRegistry.product_id)
            .filter(MarketInstrumentRegistry.venue == "coinbase")
            .filter(MarketInstrumentRegistry.product_id.in_(list(products.keys())))
            .all()
        }
        for product_id, config in products.items():
            if product_id in existing_coinbase_products:
                continue
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
                    series_exists = (
                        session.query(FredSeriesRegistry.id)
                        .filter_by(series_id=series_id)
                        .first()
                        is not None
                    )
                    if not series_exists:
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


def _seed_massive_only_regime_inputs(
    settings,
    *,
    total_15m_buckets: int = 96,
    anchor_now=None,
) -> None:
    session = get_session(settings)
    now = anchor_now or utcnow().replace(second=0, microsecond=0)
    receipt_now = utcnow().replace(second=0, microsecond=0)
    minute_start = now - timedelta(minutes=total_15m_buckets * 15)
    products = {
        "X:BTCUSD": {"base": "BTC", "price": 64000.0, "offset": 0.15},
        "X:ETHUSD": {"base": "ETH", "price": 3200.0, "offset": 0.75},
        "X:SOLUSD": {"base": "SOL", "price": 140.0, "offset": 1.35},
    }
    ingest_specs = (
        ("coinbase_products_run_200", "coinbase", "products"),
        ("coinbase_candles_run_200", "coinbase", "candles"),
        ("coinbase_trades_run_200", "coinbase", "market_trades"),
        ("coinbase_book_run_200", "coinbase", "book"),
        ("massive_minute_run_200", "massive", "minute_aggs"),
    )
    try:
        existing_runs = {
            run.run_id: run
            for run in session.query(IngestRun)
            .filter(IngestRun.run_id.in_([spec[0] for spec in ingest_specs]))
            .all()
        }
        for run_id, provider, capture_type in ingest_specs:
            existing_run = existing_runs.get(run_id)
            if existing_run is not None:
                existing_run.provider = provider
                existing_run.capture_type = capture_type
                existing_run.status = "success"
                existing_run.started_at = receipt_now
                existing_run.finished_at = receipt_now
                existing_run.records_captured = 1
                existing_run.created_at = receipt_now
                continue
            session.add(
                IngestRun(
                    run_id=run_id,
                    provider=provider,
                    capture_type=capture_type,
                    status="success",
                    started_at=receipt_now,
                    finished_at=receipt_now,
                    records_captured=1,
                    created_at=receipt_now,
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
                    checked_at=receipt_now,
                )
            )

        existing_massive_products = {
            product_id
            for (product_id,) in session.query(MarketInstrumentRegistry.product_id)
            .filter(MarketInstrumentRegistry.venue == "massive")
            .filter(MarketInstrumentRegistry.product_id.in_(list(products.keys())))
            .all()
        }
        for product_id, config in products.items():
            if product_id in existing_massive_products:
                continue
            session.add(
                MarketInstrumentRegistry(
                    venue="massive",
                    product_id=product_id,
                    base_symbol=config["base"],
                    quote_symbol="USD",
                    product_type="SPOT",
                    status="active",
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
            phase_size = max(total_minutes // 4, 1)
            phase = min(3, minute_index // phase_size)
            phase_drift = [0.00045, -0.0008, 0.00008, 0.00032][phase]
            phase_vol = [0.00035, 0.0012, 0.0002, 0.00075][phase]
            for product_id, config in products.items():
                prev_price = prices[product_id]
                signal = math.sin((minute_index / 8.0) + config["offset"])
                step_return = phase_drift + (phase_vol * signal)
                close_price = max(1.0, prev_price * (1.0 + step_return))
                high_price = max(prev_price, close_price) * (1.0 + abs(step_return) * 0.3)
                low_price = min(prev_price, close_price) * (1.0 - abs(step_return) * 0.3)
                volume = 7.0 + phase + abs(signal) * 2.0

                session.add(
                    MarketCandle(
                        ingest_run_id="massive_minute_run_200",
                        venue="massive",
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
                prices[product_id] = close_price

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


def test_cli_materializes_global_regime_with_massive_candle_fallback(cli_runner, settings) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _seed_massive_only_regime_inputs(settings)

    materialize_result = cli_runner.invoke(
        cli,
        ["materialize-features", "global-regime-inputs-15m-v1"],
    )
    assert materialize_result.exit_code == 0

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
            .order_by(FeatureGlobalRegimeInput15mV1.bucket_start_utc.asc())
            .all()
        )
    finally:
        session.close()

    assert feature_run.status == "success"
    assert len(feature_rows) >= 40
    assert any("X:BTCUSD" in (row.proxy_products_json or "") for row in feature_rows)


def test_regime_proxy_selection_stays_spot_only_with_context_derivatives(settings) -> None:
    run_migrations_to_head(settings)
    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    try:
        session.add_all(
            [
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id="BTC-USD",
                    base_symbol="BTC",
                    quote_symbol="USD",
                    product_type="SPOT",
                    status="online",
                    first_seen_at=now,
                    updated_at=now,
                ),
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id="BTC-PERP-INTX",
                    base_symbol="BTC",
                    quote_symbol="USD",
                    product_type="FUTURE",
                    status="online",
                    first_seen_at=now,
                    updated_at=now,
                ),
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id="ETH-USDC",
                    base_symbol="ETH",
                    quote_symbol="USDC",
                    product_type="SPOT",
                    status="online",
                    first_seen_at=now,
                    updated_at=now,
                ),
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id="ETH-PERP-INTX",
                    base_symbol="ETH",
                    quote_symbol="USD",
                    product_type="FUTURE",
                    status="online",
                    first_seen_at=now,
                    updated_at=now,
                ),
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id="SOL-USD",
                    base_symbol="SOL",
                    quote_symbol="USD",
                    product_type="SPOT",
                    status="online",
                    first_seen_at=now,
                    updated_at=now,
                ),
                MarketInstrumentRegistry(
                    venue="coinbase",
                    product_id="SOL-PERP-INTX",
                    base_symbol="SOL",
                    quote_symbol="USD",
                    product_type="FUTURE",
                    status="online",
                    first_seen_at=now,
                    updated_at=now,
                ),
            ]
        )
        session.commit()

        selected = FeatureMaterializer(settings)._select_regime_proxy_products(
            session.query(MarketInstrumentRegistry)
            .filter_by(venue="coinbase")
            .order_by(MarketInstrumentRegistry.product_id.asc())
            .all()
        )
    finally:
        session.close()

    assert selected == {
        "BTC": {"coinbase": "BTC-USD", "massive": "X:BTCUSD"},
        "ETH": {"coinbase": "ETH-USDC", "massive": "X:ETHUSD"},
        "SOL": {"coinbase": "SOL-USD", "massive": "X:SOLUSD"},
    }
    assert "BTC-PERP-INTX" not in set(selected["BTC"].values())
    assert "ETH-PERP-INTX" not in set(selected["ETH"].values())
    assert "SOL-PERP-INTX" not in set(selected["SOL"].values())


def test_regime_proxy_selection_falls_back_to_configured_massive_tickers(settings) -> None:
    selected = FeatureMaterializer(settings)._select_regime_proxy_products([])

    assert selected == {
        "BTC": {"massive": "X:BTCUSD"},
        "ETH": {"massive": "X:ETHUSD"},
        "SOL": {"massive": "X:SOLUSD"},
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
    settings.condition_walk_forward_refit_cadence_buckets = 4
    settings.condition_walk_forward_max_refits = 0
    settings.condition_walk_forward_max_history_days = 0

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
    # Pin the synthetic anchor away from midnight so the first same-day bucket
    # still predates the same-day FRED capture timestamp.
    anchor_now = utcnow().replace(hour=16, minute=0, second=0, microsecond=0)
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
