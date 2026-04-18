from __future__ import annotations

import json
from datetime import timedelta

import pytest

from d5_trading_engine.cli import _CAPTURE_CHOICES, cli
from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.features.materializer import _FEATURE_SET_NAME
from d5_trading_engine.storage.analytics.duckdb_mirror import DuckDBMirror
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    FeatureMaterializationRun,
    FeatureSpotChainMacroMinuteV1,
    FredObservation,
    FredSeriesRegistry,
    IngestRun,
    MarketCandle,
    MarketInstrumentRegistry,
    MarketTradeEvent,
    OrderBookL2Event,
    QuoteSnapshot,
    SolanaAddressRegistry,
    SolanaTransferEvent,
    SourceHealthEvent,
    TokenPriceSnapshot,
    TokenRegistry,
)
from tests.test_condition_scoring import _seed_global_regime_inputs


def _seed_ingest_run(settings) -> None:
    session = get_session(settings)
    now = utcnow()
    try:
        session.add(
            IngestRun(
                run_id="test_run_001",
                provider="fred",
                capture_type="series",
                status="success",
                started_at=now,
                finished_at=now,
                records_captured=1,
                created_at=now,
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_feature_inputs(
    settings,
    *,
    include_health: bool = True,
    anchor_now=None,
    current_fred_captured_at=None,
) -> None:
    session = get_session(settings)
    now = anchor_now or utcnow().replace(second=0, microsecond=0)
    try:
        for run_id, provider, capture_type in (
            ("price_run_001", "jupiter", "prices"),
            ("quote_run_001", "jupiter", "quotes"),
            ("coinbase_products_run_001", "coinbase", "products"),
            ("coinbase_candles_run_001", "coinbase", "candles"),
            ("coinbase_trades_run_001", "coinbase", "market_trades"),
            ("coinbase_book_run_001", "coinbase", "book"),
            ("helius_run_001", "helius", "enhanced_transactions"),
            ("fred_run_001", "fred", "observations"),
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
        if include_health:
            for provider, endpoint in (
                ("jupiter", "/price/v3"),
                ("jupiter", "/swap/v1/quote"),
                ("helius", "/v0/addresses/*/transactions"),
                ("coinbase", "/market/products"),
                ("coinbase", "/market/products/*/candles"),
                ("coinbase", "/market/products/*/ticker"),
                ("coinbase", "/market/product_book"),
                ("fred", "observations"),
            ):
                session.add(
                    SourceHealthEvent(
                        provider=provider,
                        endpoint=endpoint,
                        status_code=200,
                        latency_ms=120.0,
                        is_healthy=1,
                        error_message=None,
                        checked_at=now,
                    )
                )

        sol_mint = "So11111111111111111111111111111111111111112"
        usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        session.add(
            TokenRegistry(
                mint=sol_mint,
                symbol="SOL",
                name="Solana",
                decimals=9,
                logo_uri=None,
                tags=None,
                provider="jupiter",
                first_seen_at=now,
                updated_at=now,
            )
        )
        session.add(
            TokenPriceSnapshot(
                ingest_run_id="price_run_001",
                mint=sol_mint,
                symbol="SOL",
                price_usd=101.5,
                provider="jupiter",
                captured_at=now,
            )
        )
        session.add(
            QuoteSnapshot(
                ingest_run_id="quote_run_001",
                input_mint=usdc_mint,
                output_mint=sol_mint,
                input_amount="1000000",
                output_amount="985000",
                price_impact_pct=0.12,
                slippage_bps=50,
                route_plan_json="[]",
                other_amount_threshold="0",
                swap_mode="ExactIn",
                request_direction="buy",
                requested_at=now,
                response_latency_ms=150.0,
                source_event_time_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
                provider="jupiter",
                captured_at=now,
            )
        )

        session.add(
            MarketInstrumentRegistry(
                venue="coinbase",
                product_id="SOL-USD",
                base_symbol="SOL",
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
        session.add(
            MarketCandle(
                ingest_run_id="coinbase_candles_run_001",
                venue="coinbase",
                product_id="SOL-USD",
                granularity="ONE_MINUTE",
                start_time_utc=now,
                end_time_utc=None,
                open=100.0,
                high=102.0,
                low=99.0,
                close=101.0,
                volume=42.0,
                source_event_time_utc=now,
                captured_at_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
            )
        )
        session.add(
            MarketTradeEvent(
                ingest_run_id="coinbase_trades_run_001",
                venue="coinbase",
                product_id="SOL-USD",
                trade_id="trade-1",
                side="buy",
                price=101.0,
                size=2.0,
                source_event_time_utc=now,
                captured_at_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
            )
        )
        session.add(
            MarketTradeEvent(
                ingest_run_id="coinbase_trades_run_001",
                venue="coinbase",
                product_id="SOL-USD",
                trade_id="trade-2",
                side="sell",
                price=101.25,
                size=3.0,
                source_event_time_utc=now,
                captured_at_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
            )
        )
        session.add(
            OrderBookL2Event(
                ingest_run_id="coinbase_book_run_001",
                venue="coinbase",
                product_id="SOL-USD",
                event_kind="snapshot",
                best_bid=100.9,
                best_ask=101.1,
                spread_absolute=0.2,
                spread_bps=19.82,
                bids_json="[]",
                asks_json="[]",
                source_event_time_utc=now,
                captured_at_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
            )
        )

        session.add(
            SolanaAddressRegistry(
                address="tracked_wallet_001",
                label="tracked wallet",
                address_type="wallet",
                is_tracked=1,
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            SolanaTransferEvent(
                ingest_run_id="helius_run_001",
                signature="sig-1",
                slot=1,
                mint=sol_mint,
                source_address="tracked_wallet_001",
                destination_address="dest_wallet_001",
                amount_raw="2",
                amount_float=2.0,
                decimals=9,
                program_id="prog-1",
                fee_lamports=5000,
                transfer_type="token",
                source_event_time_utc=now,
                captured_at_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
            )
        )
        session.add(
            SolanaTransferEvent(
                ingest_run_id="helius_run_001",
                signature="sig-2",
                slot=2,
                mint=sol_mint,
                source_address="src_wallet_001",
                destination_address="tracked_wallet_001",
                amount_raw="4",
                amount_float=4.0,
                decimals=9,
                program_id="prog-1",
                fee_lamports=5000,
                transfer_type="token",
                source_event_time_utc=now,
                captured_at_utc=now,
                source_time_raw=now.isoformat(),
                event_date_utc=now.strftime("%Y-%m-%d"),
                hour_utc=now.hour,
                minute_of_day_utc=(now.hour * 60) + now.minute,
                weekday_utc=now.weekday(),
                time_quality="source",
            )
        )

        session.add(
            FredSeriesRegistry(
                series_id="DFF",
                title="Federal Funds Effective Rate",
                frequency="Daily",
                units="Percent",
                seasonal_adjustment=None,
                last_updated=now,
                provider="fred",
                first_seen_at=now,
                updated_at=now,
            )
        )
        session.add(
            FredObservation(
                ingest_run_id="fred_run_001",
                series_id="DFF",
                observation_date=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
                value=4.21,
                realtime_start=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
                realtime_end=(now - timedelta(days=1)).strftime("%Y-%m-%d"),
                provider="fred",
                captured_at=now - timedelta(days=1),
            )
        )
        session.add(
            FredObservation(
                ingest_run_id="fred_run_001",
                series_id="DFF",
                observation_date=now.strftime("%Y-%m-%d"),
                value=4.33,
                realtime_start=now.strftime("%Y-%m-%d"),
                realtime_end=now.strftime("%Y-%m-%d"),
                provider="fred",
                captured_at=current_fred_captured_at or now,
            )
        )
        session.commit()
    finally:
        session.close()


def test_cli_help_lists_bootstrap_commands(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "capture" in result.output
    assert "materialize-features" in result.output
    assert "score-conditions" in result.output
    assert "run-shadow" in result.output
    assert "run-backtest-walk-forward" in result.output
    assert "run-label-program" in result.output
    assert "run-strategy-eval" in result.output
    assert "run-paper-cycle" in result.output
    assert "review-proposal" in result.output
    assert "compare-proposals" in result.output
    assert "status" in result.output
    assert "sync-duckdb" in result.output


def test_cli_capture_help_lists_source_expansion_providers(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["capture", "--help"], terminal_width=200)

    assert result.exit_code == 0
    assert {
        "helius-discovery",
        "helius-ws-events",
        "coinbase-products",
        "coinbase-candles",
        "coinbase-market-trades",
        "coinbase-book",
        "massive-minute-aggs",
    } <= set(_CAPTURE_CHOICES)


def test_cli_run_shadow_help_lists_regime_model_compare(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["run-shadow", "--help"], terminal_width=200)

    assert result.exit_code == 0
    assert "intraday-meta-stack-v1" in result.output
    assert "regime-model-compare-v1" in result.output


def test_cli_init_runs_migrations(cli_runner, settings) -> None:
    result = cli_runner.invoke(cli, ["init"])

    assert result.exit_code == 0
    assert settings.db_path.exists()
    assert "migrations applied to head" in result.output


def test_cli_status_reports_empty_initialized_db(cli_runner) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "No ingest runs yet." in result.output
    assert "No health events yet." in result.output
    assert "=== Capture Lanes ===" in result.output
    assert "jupiter-prices" in result.output
    assert "never_started" in result.output
    assert "massive-crypto" in result.output
    assert "operator_reference_refresh" in result.output


def test_cli_status_reports_capture_lane_states(cli_runner, settings) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    _seed_feature_inputs(settings)

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "=== Capture Lanes ===" in result.output
    assert "jupiter-prices" in result.output
    assert "state=healthy_recent" in result.output
    assert "helius-transactions" in result.output
    assert "massive-crypto" in result.output
    assert "never_started" in result.output
    assert "required blockers=none" in result.output


def test_status_surfaces_latest_failed_condition_run(cli_runner, settings) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    try:
        session.add(
            FeatureMaterializationRun(
                run_id="feature_run_status",
                feature_set="global_regime_inputs_15m_v1",
                source_tables="[]",
                status="success",
                started_at=now - timedelta(hours=1),
                finished_at=now - timedelta(hours=1),
                created_at=now - timedelta(hours=1),
            )
        )
        session.flush()
        session.add(
            ConditionScoringRun(
                run_id="condition_success_old",
                condition_set="global_regime_v1",
                source_feature_run_id="feature_run_status",
                model_family="gaussian_hmm_4state",
                status="success",
                confidence=0.84,
                started_at=now - timedelta(minutes=40),
                finished_at=now - timedelta(minutes=39),
                created_at=now - timedelta(minutes=40),
            )
        )
        session.flush()
        session.add(
            ConditionGlobalRegimeSnapshotV1(
                condition_run_id="condition_success_old",
                source_feature_run_id="feature_run_status",
                bucket_start_utc=now - timedelta(minutes=45),
                raw_state_id=1,
                semantic_regime="long_friendly",
                confidence=0.84,
                blocked_flag=0,
                blocking_reason=None,
                model_family="gaussian_hmm_4state",
                macro_context_state="healthy_recent",
                created_at=now - timedelta(minutes=39),
            )
        )
        session.add(
            ConditionScoringRun(
                run_id="condition_failed_latest",
                condition_set="global_regime_v1",
                source_feature_run_id="feature_run_status",
                model_family="gaussian_hmm_4state",
                status="failed",
                confidence=None,
                error_message="freshness authorization failed",
                started_at=now - timedelta(minutes=5),
                finished_at=now - timedelta(minutes=4),
                created_at=now - timedelta(minutes=5),
            )
        )
        session.commit()
    finally:
        session.close()

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "latest run failed" in result.output
    assert "condition_failed_latest" in result.output
    assert "freshness authorization failed" in result.output
    assert "no current eligible snapshot from the latest run." in result.output
    assert "long_friendly" not in result.output


def test_status_shows_latest_successful_condition_snapshot(cli_runner, settings) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    _seed_global_regime_inputs(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["score-conditions", "global-regime-v1"]).exit_code == 0

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "=== Current Condition ===" in result.output
    assert "run=condition_global_regime_v1_" in result.output
    assert "feature_run=feature_global_regime_inputs_15m_v1_" in result.output


def test_cli_sync_duckdb_copies_seeded_table(cli_runner, settings) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    _seed_ingest_run(settings)

    result = cli_runner.invoke(cli, ["sync-duckdb", "ingest_run"])

    assert result.exit_code == 0
    assert "✓ ingest_run: 1 rows" in result.output

    mirror = DuckDBMirror(settings)
    try:
        rows = mirror.query("SELECT count(*) FROM ingest_run")
    finally:
        mirror.close()

    assert rows == [(1,)]


def test_cli_status_reports_coinbase_raw_db_path(cli_runner) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "Coinbase raw DB:" in result.output


def test_cli_materialize_features_writes_first_feature_rows(cli_runner, settings) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    _seed_feature_inputs(settings)

    result = cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"])

    assert result.exit_code == 0
    assert "spot_chain_macro_v1" in result.output
    assert "rows=1" in result.output

    session = get_session(settings)
    try:
        feature_run = session.query(FeatureMaterializationRun).one()
        feature_row = session.query(FeatureSpotChainMacroMinuteV1).one()
    finally:
        session.close()

    freshness_snapshot = json.loads(feature_run.freshness_snapshot_json or "{}")

    assert feature_run.feature_set == _FEATURE_SET_NAME
    assert feature_run.status == "success"
    assert feature_run.row_count == 1
    assert feature_run.input_window_start_utc == feature_row.feature_minute_utc
    assert feature_run.input_window_end_utc == feature_row.feature_minute_utc
    assert (
        freshness_snapshot["required_lanes"]["jupiter-prices"]["freshness_state"]
        == "healthy_recent"
    )
    assert (
        freshness_snapshot["required_lanes"]["coinbase-book"]["downstream_eligible"] is True
    )
    assert feature_row.symbol == "SOL"
    assert feature_row.coinbase_product_id == "SOL-USD"
    assert feature_row.jupiter_price_usd == 101.5
    assert feature_row.quote_count == 1
    assert feature_row.mean_quote_price_impact_pct == pytest.approx(0.12)
    assert feature_row.mean_quote_response_latency_ms == pytest.approx(150.0)
    assert feature_row.coinbase_close == pytest.approx(101.0)
    assert feature_row.coinbase_trade_count == 2
    assert feature_row.coinbase_trade_size_sum == pytest.approx(5.0)
    assert feature_row.coinbase_book_spread_bps == pytest.approx(19.82)
    assert feature_row.chain_transfer_count == 2
    assert feature_row.chain_amount_in == pytest.approx(4.0)
    assert feature_row.chain_amount_out == pytest.approx(2.0)
    assert feature_row.fred_dff == pytest.approx(4.33)


def test_spot_chain_materialization_respects_fred_captured_at(cli_runner, settings) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    anchor_now = utcnow().replace(second=0, microsecond=0)
    _seed_feature_inputs(
        settings,
        anchor_now=anchor_now,
        current_fred_captured_at=anchor_now + timedelta(hours=2),
    )

    result = cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"])

    assert result.exit_code == 0

    session = get_session(settings)
    try:
        feature_row = session.query(FeatureSpotChainMacroMinuteV1).one()
    finally:
        session.close()

    assert feature_row.fred_dff == pytest.approx(4.21)


def test_cli_materialize_features_fails_closed_without_health_receipts(
    cli_runner, settings
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    _seed_feature_inputs(settings, include_health=False)

    result = cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"])

    assert result.exit_code == 1
    assert "Freshness authorization failed" in result.output

    session = get_session(settings)
    try:
        feature_run = session.query(FeatureMaterializationRun).one()
    finally:
        session.close()

    freshness_snapshot = json.loads(feature_run.freshness_snapshot_json or "{}")

    assert feature_run.status == "failed"
    assert "Freshness authorization failed" in (feature_run.error_message or "")
    assert (
        freshness_snapshot["required_lanes"]["jupiter-prices"]["freshness_state"]
        == "degraded"
    )
    assert (
        freshness_snapshot["required_lanes"]["jupiter-prices"]["downstream_eligible"]
        is False
    )


def test_cli_capture_helius_transactions_requires_tracked_addresses(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["capture", "helius-transactions"])

    assert result.exit_code == 1
    assert "HELIUS_TRACKED_ADDRESSES" in result.output


def test_cli_capture_helius_ws_events_requires_tracked_addresses(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["capture", "helius-ws-events"])

    assert result.exit_code == 1
    assert "HELIUS_TRACKED_ADDRESSES" in result.output


def test_cli_capture_helius_ws_events_dispatches(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    async def _fake_capture(self) -> str:
        return "helius_ws_events_test"

    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_helius_ws_events",
        _fake_capture,
    )

    result = cli_runner.invoke(cli, ["capture", "helius-ws-events"])

    assert result.exit_code == 0
    assert "✓ Helius ws events: helius_ws_events_test" in result.output


def test_cli_capture_massive_crypto_surfaces_fail_closed_error(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    async def _raise_auth_error(self) -> list[dict]:
        raise AdapterError(
            "massive",
            "Authentication failed — check API key and plan entitlements",
            status_code=403,
        )

    async def _noop_close(self) -> None:
        return None

    monkeypatch.setattr(
        "d5_trading_engine.adapters.massive.client.MassiveClient.fetch_crypto_reference_bundle",
        _raise_auth_error,
    )
    monkeypatch.setattr(
        "d5_trading_engine.adapters.massive.client.MassiveClient.close",
        _noop_close,
    )

    result = cli_runner.invoke(cli, ["capture", "massive-crypto"])

    assert result.exit_code == 1
    assert "Massive crypto capture failed closed" in result.output


def test_cli_capture_massive_minute_aggs_requires_one_history_mode(cli_runner) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    result = cli_runner.invoke(cli, ["capture", "massive-minute-aggs"])

    assert result.exit_code == 1
    assert "Choose exactly one Massive history mode" in result.output


def test_cli_capture_massive_minute_aggs_dispatches(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    async def _fake_capture(self, date_str: str, **kwargs) -> str:
        assert date_str == "2026-04-16"
        assert kwargs == {}
        return "massive_minute_aggs_test"

    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_massive_minute_aggs",
        _fake_capture,
    )

    result = cli_runner.invoke(
        cli,
        ["capture", "massive-minute-aggs", "--date", "2026-04-16"],
    )

    assert result.exit_code == 0
    assert "✓ Massive minute aggs: massive_minute_aggs_test" in result.output


def test_cli_capture_massive_minute_aggs_full_free_tier_dispatches(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    async def _fake_backfill(self, *, resume: bool = True):
        assert resume is True
        return {
            "batch_id": "capture_batch_massive_free_tier",
            "days": {"captured_count": 5, "skipped_count": 2},
        }

    monkeypatch.setattr(
        "d5_trading_engine.capture.massive_backfill.MassiveMinuteAggsBackfill.backfill_full_free_tier",
        _fake_backfill,
    )

    result = cli_runner.invoke(
        cli,
        ["capture", "massive-minute-aggs", "--full-free-tier"],
    )

    assert result.exit_code == 0
    assert "capture_batch_massive_free_tier" in result.output


def test_cli_run_live_regime_cycle_dispatches(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    async def _fake_live_cycle(self, *, with_helius_ws: bool = False):
        assert with_helius_ws is True
        return {
            "cycle_id": "live_regime_cycle_test",
            "quote_snapshot_id": 42,
            "ready_for_paper_cycle": True,
            "proposal_status": "proposed",
        }

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.live_regime_cycle.LiveRegimeCycleRunner.run_live_regime_cycle",
        _fake_live_cycle,
    )

    result = cli_runner.invoke(
        cli,
        ["run-live-regime-cycle", "--with-helius-ws"],
    )

    assert result.exit_code == 0
    assert "live_regime_cycle_test" in result.output
    assert "ready_for_paper_cycle=True" in result.output


def test_cli_run_paper_close_dispatches_json(cli_runner, monkeypatch: pytest.MonkeyPatch) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.operator.PaperTradeOperator.close_cycle",
        lambda self, **kwargs: {
            "session_key": kwargs["session_key"],
            "artifact_dir": "/tmp/paper-close",
            "settlement_result": {
                "session_status": "closed",
                "realized_pnl_usdc": 0.5,
            },
        },
    )

    result = cli_runner.invoke(
        cli,
        [
            "run-paper-close",
            "paper_session_test",
            "--quote-snapshot-id",
            "99",
            "--reason",
            "take_profit",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["session_key"] == "paper_session_test"
    assert payload["settlement_result"]["session_status"] == "closed"


def test_cli_paper_practice_bootstrap_dispatches_json(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.practice.PaperPracticeRuntime.run_bootstrap",
        lambda self: {
            "bootstrap_id": "paper_practice_bootstrap_test",
            "profile_id": "paper_profile_test",
            "feature_run_id": "feature_test",
            "artifact_dir": "/tmp/bootstrap",
            "comparison_result": {"run_id": "comparison_test"},
        },
    )

    result = cli_runner.invoke(cli, ["run-paper-practice-bootstrap", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["bootstrap_id"] == "paper_practice_bootstrap_test"


def test_cli_paper_practice_loop_and_status_dispatch_json(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.practice.PaperPracticeRuntime.run_loop",
        lambda self, **kwargs: {
            "loop_run_id": "paper_practice_loop_test",
            "status": "completed",
            "iterations_completed": kwargs.get("max_iterations") or 0,
            "active_profile_id": "paper_profile_test",
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.practice.PaperPracticeRuntime.get_status",
        lambda self: {
            "active_profile_id": "paper_profile_test",
            "active_revision_id": "paper_profile_revision_test",
            "open_session_key": "",
            "latest_loop_status": "completed",
        },
    )

    loop_result = cli_runner.invoke(
        cli,
        ["run-paper-practice-loop", "--max-iterations", "1", "--json"],
    )
    assert loop_result.exit_code == 0
    loop_payload = json.loads(loop_result.output)
    assert loop_payload["loop_run_id"] == "paper_practice_loop_test"
    assert loop_payload["iterations_completed"] == 1

    status_result = cli_runner.invoke(cli, ["paper-practice-status", "--json"])
    assert status_result.exit_code == 0
    status_payload = json.loads(status_result.output)
    assert status_payload["active_profile_id"] == "paper_profile_test"


def test_cli_core_ladder_commands_dispatch_json(
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_result = cli_runner.invoke(cli, ["init"])
    assert init_result.exit_code == 0

    monkeypatch.setattr(
        "d5_trading_engine.features.materializer.FeatureMaterializer.materialize_global_regime_inputs_15m_v1",
        lambda self: ("feature_json_test", 128),
    )
    monkeypatch.setattr(
        "d5_trading_engine.condition.scorer.ConditionScorer.score_global_regime_v1",
        lambda self: {
            "run_id": "condition_json_test",
            "model_family": "stub_hmm",
            "latest_snapshot": {
                "semantic_regime": "long_friendly",
                "confidence": 0.81,
                "bucket_start_utc": "2026-04-18T00:00:00+00:00",
                "blocking_reason": None,
                "blocked": False,
                "macro_context_state": "healthy_recent",
            },
            "history": [],
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.research_loop.regime_model_compare.RegimeModelComparator.run_regime_model_compare_v1",
        lambda self, **kwargs: {
            "run_id": "comparison_json_test",
            "artifact_dir": "/tmp/comparison",
            "recommended_candidate": "hmm",
            "proposal_status": "proposed",
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.research_loop.live_regime_cycle.LiveRegimeCycleRunner.run_live_regime_cycle",
        lambda self, **kwargs: {
            "cycle_id": "live_cycle_json_test",
            "quote_snapshot_id": 42,
            "condition_run_id": "condition_json_test",
            "ready_for_paper_cycle": True,
            "proposal_status": "proposed",
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.operator.PaperTradeOperator.run_cycle",
        lambda self, **kwargs: {
            "session_key": "paper_session_json_test",
            "session_status": "open",
            "filled": True,
            "artifact_dir": "/tmp/paper",
            "strategy_selection": {"top_family": "trend_continuation_long_v1"},
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.paper_runtime.practice.PaperPracticeRuntime.run_backtest_walk_forward",
        lambda self: {
            "run_id": "backtest_walk_forward_test",
            "status": "completed",
            "completed_ladder": True,
            "window_count": 3,
            "artifact_dir": "/tmp/backtest",
            "active_revision_id": "paper_profile_revision_test",
            "starting_revision_id": "paper_profile_revision_start",
        },
    )

    materialize_result = cli_runner.invoke(
        cli,
        ["materialize-features", "global-regime-inputs-15m-v1", "--json"],
    )
    assert materialize_result.exit_code == 0
    assert json.loads(materialize_result.output)["feature_run_id"] == "feature_json_test"

    condition_result = cli_runner.invoke(
        cli,
        ["score-conditions", "global-regime-v1", "--json"],
    )
    assert condition_result.exit_code == 0
    assert json.loads(condition_result.output)["run_id"] == "condition_json_test"

    shadow_result = cli_runner.invoke(
        cli,
        ["run-shadow", "regime-model-compare-v1", "--json"],
    )
    assert shadow_result.exit_code == 0
    assert json.loads(shadow_result.output)["run_id"] == "comparison_json_test"

    live_result = cli_runner.invoke(
        cli,
        ["run-live-regime-cycle", "--json"],
    )
    assert live_result.exit_code == 0
    assert json.loads(live_result.output)["cycle_id"] == "live_cycle_json_test"

    paper_result = cli_runner.invoke(
        cli,
        ["run-paper-cycle", "42", "--json"],
    )
    assert paper_result.exit_code == 0
    assert json.loads(paper_result.output)["session_key"] == "paper_session_json_test"

    backtest_result = cli_runner.invoke(
        cli,
        ["run-backtest-walk-forward", "--json"],
    )
    assert backtest_result.exit_code == 0
    assert json.loads(backtest_result.output)["run_id"] == "backtest_walk_forward_test"
