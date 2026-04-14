from __future__ import annotations

import pytest

from d5_trading_engine.cli import _CAPTURE_CHOICES, cli
from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.storage.analytics.duckdb_mirror import DuckDBMirror
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import IngestRun


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


def test_cli_help_lists_bootstrap_commands(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "init" in result.output
    assert "capture" in result.output
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
    } <= set(_CAPTURE_CHOICES)


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
        "d5_trading_engine.adapters.massive.client.MassiveClient.fetch_crypto_reference",
        _raise_auth_error,
    )
    monkeypatch.setattr(
        "d5_trading_engine.adapters.massive.client.MassiveClient.close",
        _noop_close,
    )

    result = cli_runner.invoke(cli, ["capture", "massive-crypto"])

    assert result.exit_code == 1
    assert "Massive crypto capture failed closed" in result.output
