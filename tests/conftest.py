from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.coinbase_raw.engine import reset_engine as reset_coinbase_raw_engine
from d5_trading_engine.storage.truth.engine import reset_engine

REPO_ROOT = Path(__file__).resolve().parents[1]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run live integration tests that hit external providers",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live external-provider integration tests",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(reason="need --run-integration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def isolate_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Keep tests off the real repo `.env` and runtime data paths."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "data" / "db" / "d5.db"))
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "data" / "db" / "d5_analytics.duckdb"))
    monkeypatch.setenv("COINBASE_RAW_DB_PATH", str(tmp_path / "data" / "db" / "coinbase_raw.db"))
    for key in (
        "SOLANA_PRIVATE_KEY",
        "QUICKNODES_HTTPS",
        "QUICKNODES_WSS",
        "ALCHEMY_HTTPS",
        "JUPITER_API_KEY",
        "HELIUS_API_KEY",
        "HELIUS_SENDER_HTTP",
        "HELIUS_TIPS",
        "HELIUS_TRACKED_ADDRESSES",
        "COINBASE_API_KEY",
        "COINBASE_API_SECRET",
        "COINBASE_API_PASSPHRASE",
        "COINBASE_SECRETS_FILE",
        "MASSIVE_API_KEY",
        "MASSIVE_FLATFILES_KEY",
        "FRED_API_KEY",
    ):
        monkeypatch.setenv(key, "")

    get_settings.cache_clear()
    reset_engine()
    reset_coinbase_raw_engine()
    yield
    reset_engine()
    reset_coinbase_raw_engine()
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()
