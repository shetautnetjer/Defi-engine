from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.coinbase_raw.engine import reset_engine as reset_coinbase_raw_engine
from d5_trading_engine.storage.truth.engine import reset_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
_MINIMAL_RESEARCH_PROFILES_TOML = """\
[meta]
version = "v1"
owner = "tests"
purpose = "Training and autoresearch profiles only; not runtime strategy or risk authority."
default_authority = "proposal_only"
default_status = "active"

[defaults]
authority = "proposal_only"
status = "active"
exploration = "balanced"
cost_sensitivity = "balanced_cost"
max_concurrent_experiments = 1
max_daily_proposals = 3
requires_qmd_receipt = true
requires_sql_metrics = true

[profiles.execution_cost_minimizer]
market_style = "execution"
time_horizon = "intraday"
market_focus = ["spot", "majors"]
cost_sensitivity = "ultra_cost_sensitive"
exploration = "conservative"
authority = "proposal_only"
preferred_sources = ["jupiter", "massive"]
preferred_surfaces = ["execution_fill", "report_diagnostic"]
preferred_features = ["spread", "route_hops"]
preferred_labels = ["tb_60m_atr1x_v1"]
preferred_metrics = ["fill_quality", "turnover_cost"]
disfavored_conditions = ["route_instability"]
primary_objective = "Prefer fewer, cleaner trades when cost is the edge killer."
hypothesis_templates = ["Reducing cost drag can dominate raw signal improvements."]
"""
_MINIMAL_RESEARCH_PROFILE_SCHEMA = """\
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://d5.local/schemas/profile.schema.json",
  "title": "D5 Training Profiles File",
  "type": "object"
}
"""


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
def isolate_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    request: pytest.FixtureRequest,
):
    """Keep tests off the real repo `.env` and runtime data paths."""
    run_integration = request.config.getoption("--run-integration")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DB_PATH", str(tmp_path / "data" / "db" / "d5.db"))
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "data" / "db" / "d5_analytics.duckdb"))
    monkeypatch.setenv("COINBASE_RAW_DB_PATH", str(tmp_path / "data" / "db" / "coinbase_raw.db"))
    (tmp_path / ".ai" / "schemas").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".ai" / "profiles.toml").write_text(_MINIMAL_RESEARCH_PROFILES_TOML, encoding="utf-8")
    (tmp_path / ".ai" / "schemas" / "profile.schema.json").write_text(
        _MINIMAL_RESEARCH_PROFILE_SCHEMA,
        encoding="utf-8",
    )
    if not run_integration:
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
            "MASSIVE_FLATFILES_SECRET",
            "FRED_API_KEY",
        ):
            monkeypatch.setenv(key, "")
        monkeypatch.setenv("TRADER_RESEARCH_PROFILE", "execution_cost_minimizer")

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
