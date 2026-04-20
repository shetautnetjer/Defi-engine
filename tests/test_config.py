from __future__ import annotations

from pathlib import Path

import pytest

from d5_trading_engine.config.settings import Settings, get_settings


def _env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, _ = stripped.partition("=")
        keys.add(key)
    return keys


def test_settings_allow_missing_provider_keys_for_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("DB_PATH", raising=False)
    monkeypatch.delenv("DUCKDB_PATH", raising=False)
    get_settings.cache_clear()

    settings = Settings(_env_file=None)

    assert settings.jupiter_api_key == ""
    assert settings.helius_api_key == ""
    assert settings.massive_api_key == ""
    assert settings.massive_flatfiles_key == ""
    assert settings.massive_flatfiles_secret == ""
    assert settings.fred_api_key == ""
    assert settings.db_path.name == "d5.db"
    assert settings.db_url == f"sqlite:///{settings.db_path}"


def test_get_settings_reads_runtime_path_overrides(settings: Settings, tmp_path: Path) -> None:
    assert settings.data_dir == tmp_path / "data"
    assert settings.db_path == tmp_path / "data" / "db" / "d5.db"
    assert settings.duckdb_path == tmp_path / "data" / "db" / "d5_analytics.duckdb"
    assert settings.coinbase_raw_db_path == tmp_path / "data" / "db" / "coinbase_raw.db"
    assert settings.db_url == f"sqlite:///{settings.db_path}"


def test_settings_parse_helius_tracked_addresses_from_comma_separated_env() -> None:
    settings = Settings(
        _env_file=None,
        helius_tracked_addresses="wallet_1, wallet_2 ,wallet_3",
    )

    assert settings.helius_tracked_addresses == ["wallet_1", "wallet_2", "wallet_3"]


def test_settings_accept_named_paper_practice_training_profile() -> None:
    settings = Settings(
        _env_file=None,
        paper_practice_training_profile="quickstart_300d",
    )

    assert settings.paper_practice_training_profile == "quickstart_300d"


def test_settings_default_paper_practice_training_profile_is_auto() -> None:
    settings = Settings(_env_file=None)

    assert settings.paper_practice_training_profile == "auto"


def test_settings_expose_training_refit_cadences() -> None:
    settings = Settings(_env_file=None)

    assert settings.condition_walk_forward_refit_cadence_buckets == 672
    assert settings.condition_walk_forward_max_history_days == 300
    assert settings.condition_walk_forward_max_refits == 8
    assert settings.regime_compare_refit_cadence_buckets == 672
    assert settings.regime_compare_max_refits == 8


def test_settings_accept_named_trader_research_profile() -> None:
    settings = Settings(
        _env_file=None,
        trader_research_profile="wallet_flow_follower",
    )

    assert settings.trader_research_profile == "wallet_flow_follower"


def test_settings_parse_helius_tracked_addresses_from_dotenv_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("HELIUS_TRACKED_ADDRESSES=wallet_1, wallet_2 ,wallet_3\n")
    monkeypatch.delenv("HELIUS_TRACKED_ADDRESSES", raising=False)

    settings = Settings(_env_file=env_file)

    assert settings.helius_tracked_addresses == ["wallet_1", "wallet_2", "wallet_3"]


def test_settings_load_coinbase_credentials_from_secrets_file(tmp_path: Path) -> None:
    secrets_file = tmp_path / "coinbase-secrets"
    secrets_file.write_text(
        "\n".join(
            [
                "# local credentials",
                "COINBASE_API_KEY=test-key",
                "COINBASE_API_SECRET=test-secret",
                "COINBASE_API_PASSPHRASE=test-passphrase",
            ]
        )
    )

    settings = Settings(
        _env_file=None,
        coinbase_secrets_file=str(secrets_file),
    )

    assert settings.coinbase_api_key == "test-key"
    assert settings.coinbase_api_secret == "test-secret"
    assert settings.coinbase_api_passphrase == "test-passphrase"
    assert settings.coinbase_auth_mode == "exchange_key"


def test_settings_load_coinbase_cdp_credentials_from_simple_key_export(tmp_path: Path) -> None:
    secrets_file = tmp_path / "coinbase-secrets"
    secrets_file.write_text(
        "\n".join(
            [
                "organizations/test-org/apiKeys/test-key",
                "",
                "-----BEGIN EC PRIVATE KEY-----\\nline-1\\nline-2\\n-----END EC PRIVATE KEY-----",
                "",
                "frontend-key-test",
            ]
        )
    )

    settings = Settings(
        _env_file=None,
        coinbase_secrets_file=str(secrets_file),
    )

    assert settings.coinbase_cdp_api_key_name == "organizations/test-org/apiKeys/test-key"
    assert settings.coinbase_cdp_api_private_key.startswith("-----BEGIN EC PRIVATE KEY-----\n")
    assert settings.coinbase_cdp_api_private_key.endswith("-----END EC PRIVATE KEY-----\n")
    assert settings.coinbase_client_api_key == "frontend-key-test"
    assert settings.coinbase_auth_mode == "cdp_app_jwt"


def test_env_example_keys_map_to_settings_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    example_keys = _env_keys(repo_root / ".env.example")
    settings_keys = {name.upper() for name in Settings.model_fields}

    assert example_keys
    assert example_keys <= settings_keys
    assert {
        "JUPITER_API_KEY",
        "JUPITER_MIN_REQUEST_INTERVAL_SECONDS",
        "HELIUS_API_KEY",
        "HELIUS_TRACKED_ADDRESSES",
        "HELIUS_WS_MAX_MESSAGES",
        "COINBASE_API_KEY",
        "COINBASE_API_SECRET",
        "COINBASE_API_PASSPHRASE",
        "COINBASE_CDP_API_KEY_NAME",
        "COINBASE_CDP_API_PRIVATE_KEY",
        "COINBASE_CLIENT_API_KEY",
        "COINBASE_SECRETS_FILE",
        "COINBASE_RAW_DB_PATH",
        "MASSIVE_API_KEY",
        "MASSIVE_FLATFILES_KEY",
        "MASSIVE_FLATFILES_SECRET",
        "PAPER_PRACTICE_TRAINING_PROFILE",
        "TRADER_RESEARCH_PROFILE",
        "FRED_API_KEY",
    } <= example_keys


def test_token_universe_defaults_to_pinned_mints() -> None:
    settings = Settings(_env_file=None)

    assert settings.token_universe == [
        "So11111111111111111111111111111111111111112",
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq",
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "zBTCug3er3tLyffELcvDNrKkCymbPWysGcWihESYfLg",
        "98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g",
        "PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF",
    ]
