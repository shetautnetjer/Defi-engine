from __future__ import annotations

import os
from pathlib import Path

import pytest

from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.analytics.duckdb_mirror import DuckDBMirror
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    IngestRun,
    RawJupiterPriceResponse,
    RawJupiterTokenResponse,
    SourceHealthEvent,
    TokenPriceSnapshot,
    TokenRegistry,
)

REPO_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_jupiter_tokens_and_prices_end_to_end(tmp_path) -> None:
    env_settings = Settings(_env_file=REPO_ENV_FILE if REPO_ENV_FILE.exists() else None)
    api_key = (
        os.environ.get("JUPITER_API_KEY", "").strip()
        or env_settings.jupiter_api_key.strip()
        or get_settings().jupiter_api_key.strip()
    )
    if not api_key:
        pytest.skip("JUPITER_API_KEY is required for live Jupiter integration tests")

    data_dir = tmp_path / "data"
    settings = Settings(
        _env_file=None,
        jupiter_api_key=api_key,
        data_dir=data_dir,
        db_path=data_dir / "db" / "d5.db",
        duckdb_path=data_dir / "db" / "d5_analytics.duckdb",
    )

    run_migrations_to_head(settings)

    runner = CaptureRunner(settings)
    token_run_id = await runner.capture_jupiter_tokens()
    price_run_id = await runner.capture_jupiter_prices()

    assert token_run_id
    assert price_run_id
    assert settings.db_path.exists()

    raw_files = list((settings.raw_dir / "jupiter").rglob("*.jsonl"))
    assert any(path.name.startswith("tokens_") for path in raw_files)
    assert any(path.name.startswith("prices_") for path in raw_files)

    session = get_session(settings)
    try:
        assert session.query(IngestRun).count() >= 2
        assert session.query(SourceHealthEvent).count() >= 2
        assert session.query(RawJupiterTokenResponse).count() >= 1
        assert session.query(RawJupiterPriceResponse).count() >= 1
        assert session.query(TokenRegistry).count() > 0
        assert session.query(TokenPriceSnapshot).count() > 0
    finally:
        session.close()

    mirror = DuckDBMirror(settings)
    try:
        assert mirror.sync_from_sqlite("ingest_run") >= 2
        assert mirror.sync_from_sqlite("source_health_event") >= 2
        assert mirror.sync_from_sqlite("token_registry") > 0
        assert mirror.sync_from_sqlite("token_price_snapshot") > 0
        assert mirror.query("SELECT count(*) FROM token_registry")[0][0] > 0
        assert mirror.query("SELECT count(*) FROM token_price_snapshot")[0][0] > 0
    finally:
        mirror.close()

    assert settings.duckdb_path.exists()
