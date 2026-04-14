from __future__ import annotations

import os
from pathlib import Path

import pytest

from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.common.errors import CaptureError
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.analytics.duckdb_mirror import DuckDBMirror
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    IngestRun,
    ProgramRegistry,
    RawHeliusAccountDiscovery,
    RawHeliusEnhancedTransaction,
    RawHeliusWsEvent,
    SolanaAddressRegistry,
    SolanaTransferEvent,
    SourceHealthEvent,
)

REPO_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _resolve_live_helius_config() -> tuple[str, list[str]]:
    env_settings = Settings(_env_file=REPO_ENV_FILE if REPO_ENV_FILE.exists() else None)
    api_key = (
        os.environ.get("HELIUS_API_KEY", "").strip()
        or env_settings.helius_api_key.strip()
        or get_settings().helius_api_key.strip()
    )
    tracked_addresses = (
        os.environ.get("HELIUS_TRACKED_ADDRESSES", "").strip()
        or ",".join(env_settings.helius_tracked_addresses)
        or ",".join(get_settings().helius_tracked_addresses)
    )

    if not api_key:
        pytest.skip("HELIUS_API_KEY is required for live Helius integration tests")

    addresses = [address.strip() for address in tracked_addresses.split(",") if address.strip()]
    if not addresses:
        pytest.skip("HELIUS_TRACKED_ADDRESSES is required for live Helius integration tests")

    return api_key, addresses


@pytest.mark.integration
@pytest.mark.asyncio
async def test_helius_discovery_and_transactions_end_to_end(tmp_path) -> None:
    api_key, tracked_addresses = _resolve_live_helius_config()

    data_dir = tmp_path / "data"
    settings = Settings(
        _env_file=None,
        helius_api_key=api_key,
        helius_tracked_addresses=tracked_addresses,
        data_dir=data_dir,
        db_path=data_dir / "db" / "d5.db",
        duckdb_path=data_dir / "db" / "d5_analytics.duckdb",
    )

    run_migrations_to_head(settings)

    runner = CaptureRunner(settings)
    discovery_run_id = await runner.capture_helius_discovery()
    transaction_run_id = await runner.capture_helius_transactions()

    assert discovery_run_id
    assert transaction_run_id
    assert settings.db_path.exists()

    raw_files = list((settings.raw_dir / "helius").rglob("*.jsonl"))
    assert any(path.name.startswith("account_discovery_") for path in raw_files)
    assert any(path.name.startswith("enhanced_tx_") for path in raw_files)

    session = get_session(settings)
    try:
        assert session.query(IngestRun).count() >= 2
        assert session.query(SourceHealthEvent).count() >= 2
        assert session.query(RawHeliusAccountDiscovery).count() >= 1
        assert session.query(RawHeliusEnhancedTransaction).count() >= 1
        assert session.query(ProgramRegistry).count() >= 1
        assert session.query(SolanaAddressRegistry).count() >= 1
        assert session.query(SolanaTransferEvent).count() >= 1
    finally:
        session.close()

    mirror = DuckDBMirror(settings)
    try:
        assert mirror.sync_from_sqlite("ingest_run") >= 2
        assert mirror.sync_from_sqlite("source_health_event") >= 2
        assert mirror.sync_from_sqlite("program_registry") >= 1
        assert mirror.sync_from_sqlite("solana_address_registry") >= 1
        assert mirror.sync_from_sqlite("solana_transfer_event") >= 1
        assert mirror.query("SELECT count(*) FROM program_registry")[0][0] >= 1
        assert mirror.query("SELECT count(*) FROM solana_address_registry")[0][0] >= 1
        assert mirror.query("SELECT count(*) FROM solana_transfer_event")[0][0] >= 1
    finally:
        mirror.close()

    assert settings.duckdb_path.exists()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_helius_ws_events_end_to_end(tmp_path) -> None:
    api_key, tracked_addresses = _resolve_live_helius_config()

    data_dir = tmp_path / "data"
    settings = Settings(
        _env_file=None,
        helius_api_key=api_key,
        helius_tracked_addresses=tracked_addresses,
        helius_ws_max_messages=1,
        data_dir=data_dir,
        db_path=data_dir / "db" / "d5.db",
        duckdb_path=data_dir / "db" / "d5_analytics.duckdb",
    )

    run_migrations_to_head(settings)

    runner = CaptureRunner(settings)
    try:
        run_id = await runner.capture_helius_ws_events()
    except CaptureError as exc:
        message = str(exc)
        if "not available on the free plan" in message:
            pytest.skip(
                "Helius transactionSubscribe is not enabled for the configured plan",
            )
        if "before reaching 1" in message or "timed out" in message:
            pytest.skip(
                "No live Helius websocket notification arrived for the tracked "
                "addresses during the bounded test window",
            )
        raise

    assert run_id

    raw_files = list((settings.raw_dir / "helius").rglob("*.jsonl"))
    assert any(path.name.startswith("ws_event_") for path in raw_files)

    session = get_session(settings)
    try:
        assert session.query(IngestRun).count() >= 1
        assert session.query(SourceHealthEvent).count() >= 1
        assert session.query(RawHeliusWsEvent).count() >= 2
        event_types = {
            event_type
            for (event_type,) in session.query(RawHeliusWsEvent.event_type).all()
        }
        assert "subscription_ack" in event_types
        assert "transactionNotification" in event_types
        ingest_run = session.query(IngestRun).filter_by(run_id=run_id).one()
        assert ingest_run.status == "success"
        assert ingest_run.records_captured == 1
    finally:
        session.close()
