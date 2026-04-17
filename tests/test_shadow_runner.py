from __future__ import annotations

import json
import math

from d5_trading_engine.cli import cli
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.research_loop.shadow_runner import _SHADOW_RUN_NAME
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ExperimentMetric,
    ExperimentRun,
    IngestRun,
    MarketCandle,
    QuoteSnapshot,
    SolanaAddressRegistry,
    SolanaTransferEvent,
    SourceHealthEvent,
    TokenPriceSnapshot,
    TokenRegistry,
)
from tests.test_condition_scoring import _seed_global_regime_inputs


def _seed_shadow_feature_inputs(settings) -> None:
    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    sol_mint = next(
        mint for mint, symbol in settings.token_symbol_hints.items() if symbol == "SOL"
    )
    usdc_mint = next(
        mint for mint, symbol in settings.token_symbol_hints.items() if symbol == "USDC"
    )
    try:
        for run_id, provider, capture_type in (
            ("jupiter_price_run_shadow", "jupiter", "prices"),
            ("jupiter_quote_run_shadow", "jupiter", "quotes"),
            ("helius_run_shadow", "helius", "enhanced_transactions"),
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

        for provider, endpoint in (
            ("jupiter", "/price/v3"),
            ("jupiter", "/swap/v1/quote"),
            ("helius", "/v0/addresses/*/transactions"),
        ):
            session.add(
                SourceHealthEvent(
                    provider=provider,
                    endpoint=endpoint,
                    status_code=200,
                    latency_ms=95.0,
                    is_healthy=1,
                    error_message=None,
                    checked_at=now,
                )
            )

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
            SolanaAddressRegistry(
                address="tracked_wallet_shadow",
                label="shadow wallet",
                address_type="wallet",
                is_tracked=1,
                created_at=now,
                updated_at=now,
            )
        )

        candle_rows = (
            session.query(MarketCandle)
            .filter_by(product_id="SOL-USD")
            .order_by(MarketCandle.start_time_utc.asc())
            .all()
        )
        assert candle_rows, "seed global regime inputs before shadow feature inputs"

        for index, candle in enumerate(candle_rows):
            ts = ensure_utc(candle.start_time_utc)
            assert ts is not None
            close_price = float(candle.close or 0.0)
            jupiter_price = close_price * (1.0 + (0.0003 * math.sin(index / 17.0)))
            output_amount = int((1_000_000 / max(jupiter_price, 1e-6)) * 1_000_000)
            price_impact = 0.03 + (0.015 * abs(math.sin(index / 13.0)))
            latency_ms = 60.0 + (12.0 * abs(math.cos(index / 19.0)))

            session.add(
                TokenPriceSnapshot(
                    ingest_run_id="jupiter_price_run_shadow",
                    mint=sol_mint,
                    symbol="SOL",
                    price_usd=jupiter_price,
                    provider="jupiter",
                    captured_at=ts,
                )
            )
            session.add(
                QuoteSnapshot(
                    ingest_run_id="jupiter_quote_run_shadow",
                    input_mint=usdc_mint,
                    output_mint=sol_mint,
                    input_amount="1000000",
                    output_amount=str(output_amount),
                    price_impact_pct=price_impact,
                    slippage_bps=50,
                    route_plan_json="[]",
                    other_amount_threshold="0",
                    swap_mode="ExactIn",
                    request_direction="buy",
                    requested_at=ts,
                    response_latency_ms=latency_ms,
                    source_event_time_utc=ts,
                    source_time_raw=ts.isoformat(),
                    event_date_utc=ts.strftime("%Y-%m-%d"),
                    hour_utc=ts.hour,
                    minute_of_day_utc=(ts.hour * 60) + ts.minute,
                    weekday_utc=ts.weekday(),
                    time_quality="source",
                    provider="jupiter",
                    captured_at=ts,
                )
            )
            session.add(
                SolanaTransferEvent(
                    ingest_run_id="helius_run_shadow",
                    signature=f"shadow-out-{index}",
                    slot=1_000 + index,
                    mint=sol_mint,
                    source_address="tracked_wallet_shadow",
                    destination_address=f"shadow-dest-{index}",
                    amount_raw=str(1_500 + index),
                    amount_float=1.5 + (index * 0.01),
                    decimals=9,
                    program_id="shadow-prog",
                    fee_lamports=5_000,
                    transfer_type="token",
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
                SolanaTransferEvent(
                    ingest_run_id="helius_run_shadow",
                    signature=f"shadow-in-{index}",
                    slot=2_000 + index,
                    mint=sol_mint,
                    source_address=f"shadow-src-{index}",
                    destination_address="tracked_wallet_shadow",
                    amount_raw=str(2_000 + index),
                    amount_float=2.0 + (index * 0.01),
                    decimals=9,
                    program_id="shadow-prog",
                    fee_lamports=5_000,
                    transfer_type="token",
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

        session.commit()
    finally:
        session.close()


class _FakeChronosPipeline:
    quantiles = [0.1, 0.5, 0.9]

    def predict(self, contexts, prediction_length: int, context_length: int):
        del context_length
        import numpy as np
        import torch

        base = float(contexts[0][-1])
        steps = np.arange(1, prediction_length + 1, dtype=float)
        median = base * (1.0 + (0.0012 * steps))
        lower = median * 0.995
        upper = median * 1.005
        forecast = np.stack([lower, median, upper])[None, ...]
        return torch.from_numpy(forecast).to(dtype=torch.float32)


def _prepare_shadow_runtime(settings) -> None:
    _seed_global_regime_inputs(settings)
    _seed_shadow_feature_inputs(settings)


def test_cli_run_shadow_persists_receipts_and_artifacts(cli_runner, settings, monkeypatch) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _prepare_shadow_runtime(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"]).exit_code == 0

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.shadow_runner.ShadowRunner._load_chronos_pipeline",
        lambda self: _FakeChronosPipeline(),
    )

    result = cli_runner.invoke(cli, ["run-shadow", "intraday-meta-stack-v1"])
    assert result.exit_code == 0
    assert "intraday_meta_stack_v1" in result.output
    assert "chronos=ok" in result.output

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).one()
        metrics = session.query(ExperimentMetric).all()
    finally:
        session.close()

    config = json.loads(run.config_json or "{}")
    artifact_dir = settings.data_dir / "research" / "shadow_runs" / run.run_id

    assert run.experiment_name == _SHADOW_RUN_NAME
    assert run.status == "success"
    assert "chronos=ok" in (run.conclusion or "")
    assert config["shadow_run"] == _SHADOW_RUN_NAME
    assert config["regime_history_mode"] == "walk_forward"
    assert config["regime_refit_cadence_buckets"] == 4
    assert config["regime_training_window_days"] == 90
    assert artifact_dir.exists()
    assert (artifact_dir / "config.json").exists()
    assert (artifact_dir / "chronos_summary.json").exists()
    assert (artifact_dir / "model_metrics.json").exists()
    assert (artifact_dir / "dataset_preview.json").exists()
    assert (artifact_dir / "report.qmd").exists()
    assert any(metric.metric_name == "dataset_rows" for metric in metrics)
    assert any(metric.metric_name == "anomaly_rate" for metric in metrics)
    assert any(metric.metric_name.endswith("_rf_accuracy") for metric in metrics)
    assert any(metric.metric_name.endswith("_xgb_accuracy") for metric in metrics)


def test_cli_run_shadow_succeeds_when_chronos_is_unavailable(
    cli_runner,
    settings,
    monkeypatch,
) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _prepare_shadow_runtime(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"]).exit_code == 0

    def _raise_chronos(self):
        raise ModuleNotFoundError("chronos unavailable in test")

    monkeypatch.setattr(
        "d5_trading_engine.research_loop.shadow_runner.ShadowRunner._load_chronos_pipeline",
        _raise_chronos,
    )

    result = cli_runner.invoke(cli, ["run-shadow", "intraday-meta-stack-v1"])
    assert result.exit_code == 0
    assert "chronos=skipped:ModuleNotFoundError" in result.output

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).one()
    finally:
        session.close()

    assert run.status == "success"
    assert "chronos=skipped:ModuleNotFoundError" in (run.conclusion or "")
    config = json.loads(run.config_json or "{}")
    assert config["regime_history_mode"] == "walk_forward"
