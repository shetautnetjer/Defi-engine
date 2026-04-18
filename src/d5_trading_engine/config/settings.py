"""
D5 Trading Engine — Settings

Environment-based configuration using pydantic-settings.
Reads from .env file. Never prints or logs secret values.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_SOL_MINT = "So11111111111111111111111111111111111111112"
_DEFAULT_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _parse_env_secrets_file(path: Path) -> dict[str, str]:
    """Read a simple KEY=VALUE secrets file without logging sensitive data."""
    if not path.exists() or not path.is_file():
        return {}

    parsed: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, separator, value = stripped.partition("=")
        if not separator:
            continue
        parsed[key.strip()] = value.strip().strip("\"'")
    return parsed


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Solana (reserved — inert in v0) ---
    solana_private_key: str = Field(
        default="",
        description="Reserved for future sender scaffolding. Inert.",
    )

    # --- RPC Providers ---
    quicknodes_https: str = Field(default="", description="QuickNode HTTPS endpoint")
    quicknodes_wss: str = Field(default="", description="QuickNode WSS endpoint")
    alchemy_https: str = Field(default="", description="Alchemy HTTPS endpoint")

    # --- Jupiter ---
    jupiter_api_key: str = Field(default="", description="Jupiter Developer Platform API key")
    jupiter_min_request_interval_seconds: float = Field(
        default=2.0,
        description="Minimum spacing between live Jupiter API requests.",
    )

    # --- Helius ---
    helius_api_key: str = Field(default="", description="Helius API key")
    helius_sender_http: str = Field(default="", description="Helius sender HTTP endpoint")
    helius_tips: str = Field(default="", description="Helius tips config")
    helius_ws_max_messages: int = Field(
        default=25,
        description="Bounded message count for Helius websocket raw capture runs.",
    )

    # --- Coinbase ---
    coinbase_api_key: str = Field(default="", description="Coinbase API key")
    coinbase_api_secret: str = Field(default="", description="Coinbase API secret")
    coinbase_api_passphrase: str = Field(default="", description="Coinbase API passphrase")
    coinbase_secrets_file: Path | None = Field(
        default=None,
        description="Optional local file containing Coinbase credentials.",
    )
    coinbase_candle_history_minutes: int = Field(
        default=600,
        description=(
            "Bounded one-minute Coinbase candle history requested per product so regime "
            "scoring has enough closed 15-minute buckets for paper trading."
        ),
    )

    # --- Massive ---
    massive_api_key: str = Field(default="", description="Massive REST API key")
    massive_flatfiles_key: str = Field(
        default="",
        description="Massive S3-compatible flat files key",
    )
    massive_default_tickers: list[str] = Field(
        default=["X:SOLUSD", "X:BTCUSD", "X:ETHUSD"],
        description="Default Massive crypto tickers for bounded reference and snapshot capture.",
    )

    # --- FRED ---
    fred_api_key: str = Field(default="", description="FRED API key")

    # --- Paths ---
    data_dir: Path = Field(default=_PROJECT_ROOT / "data", description="Root data directory")
    repo_root: Path = Field(
        default=_PROJECT_ROOT,
        description="Repo root for swarm policy files, docs, and backlog truth.",
    )
    db_path: Path = Field(
        default=_PROJECT_ROOT / "data" / "db" / "d5.db",
        description="SQLite database path",
    )
    duckdb_path: Path = Field(
        default=_PROJECT_ROOT / "data" / "db" / "d5_analytics.duckdb",
        description="DuckDB analytics database path",
    )
    coinbase_raw_db_path: Path = Field(
        default=_PROJECT_ROOT / "data" / "db" / "coinbase_raw.db",
        description="Separate raw SQLite database for Coinbase payload capture.",
    )

    # --- Logging ---
    log_level: str = Field(default="INFO", description="Log level")

    # --- Universe ---
    token_universe: list[str] = Field(
        default=[
            _DEFAULT_SOL_MINT,
            _DEFAULT_USDC_MINT,
            "ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq",
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "zBTCug3er3tLyffELcvDNrKkCymbPWysGcWihESYfLg",
            "98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g",
            "PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF",
        ],
        description="Pinned mint addresses for the tracked Solana spot universe.",
    )
    quote_amounts_lamports: list[int] = Field(
        default=[1_000_000, 10_000_000, 100_000_000, 1_000_000_000],
        description="Quote sizes in base units for Jupiter quote snapshots.",
    )

    # --- FRED default series ---
    fred_default_series: list[str] = Field(
        default=["DFF", "T10Y2Y", "VIXCLS", "DGS10", "DTWEXBGS"],
        description="Default FRED series IDs to track",
    )

    # --- Helius tracked addresses ---
    helius_tracked_addresses: Annotated[list[str], NoDecode] = Field(
        default=[],
        description="Solana addresses to track via Helius discovery and transaction capture.",
    )

    @field_validator("helius_tracked_addresses", mode="before")
    @classmethod
    def _parse_helius_tracked_addresses(cls, value: object) -> object:
        """Allow a simple comma-separated env var for tracked addresses."""
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @field_validator("coinbase_secrets_file", mode="before")
    @classmethod
    def _parse_coinbase_secrets_file(cls, value: object) -> object:
        """Normalize blank values and allow a simple string path."""
        if value in (None, ""):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            return Path(stripped).expanduser()
        return value

    @model_validator(mode="after")
    def _load_coinbase_secrets_file(self) -> Settings:
        """Populate Coinbase credentials from an env-like secrets file when present."""
        if self.coinbase_secrets_file is None:
            return self

        parsed = _parse_env_secrets_file(self.coinbase_secrets_file)
        self.coinbase_api_key = self.coinbase_api_key or parsed.get("COINBASE_API_KEY", "")
        self.coinbase_api_secret = self.coinbase_api_secret or parsed.get(
            "COINBASE_API_SECRET",
            "",
        )
        self.coinbase_api_passphrase = self.coinbase_api_passphrase or parsed.get(
            "COINBASE_API_PASSPHRASE",
            "",
        )
        return self

    @property
    def db_url(self) -> str:
        """SQLAlchemy database URL."""
        return f"sqlite:///{self.db_path}"

    @property
    def raw_dir(self) -> Path:
        """Raw data landing directory."""
        return self.data_dir / "raw"

    @property
    def parquet_dir(self) -> Path:
        """Parquet data directory."""
        return self.data_dir / "parquet"

    @property
    def helius_wss_url(self) -> str:
        """Helius WebSocket URL (constructed from API key)."""
        return f"wss://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"

    @property
    def helius_rpc_url(self) -> str:
        """Helius RPC URL."""
        return f"https://mainnet.helius-rpc.com/?api-key={self.helius_api_key}"

    @property
    def helius_api_base(self) -> str:
        """Helius enhanced API base URL."""
        return "https://api-mainnet.helius-rpc.com"

    @property
    def jupiter_api_base(self) -> str:
        """Jupiter API base URL."""
        return "https://api.jup.ag"

    @property
    def coinbase_api_base(self) -> str:
        """Coinbase Advanced Trade API base URL."""
        return "https://api.coinbase.com/api/v3/brokerage"

    @property
    def massive_api_base(self) -> str:
        """Massive REST API base URL."""
        return "https://api.massive.com"

    @property
    def massive_flatfiles_base(self) -> str:
        """Massive flat-file host for daily downloadable crypto data."""
        return "https://files.massive.com"

    @property
    def token_symbol_hints(self) -> dict[str, str]:
        """Stable symbol hints for the pinned mint universe."""
        return {
            _DEFAULT_SOL_MINT: "SOL",
            _DEFAULT_USDC_MINT: "USDC",
            "ZEUS1aR7aX8DFFJf5QjWj2ftDDdNTroMNGo8YoQm3Gq": "ZEUS",
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": "JUP",
            "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": "BONK",
            "zBTCug3er3tLyffELcvDNrKkCymbPWysGcWihESYfLg": "zBTC",
            "98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g": "HYPE",
            "PreweJYECqtQwBtpxHL171nL2K6umo692gTm7Q3rpgF": "OPENAI",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
