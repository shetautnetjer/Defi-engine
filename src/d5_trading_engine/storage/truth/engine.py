"""
D5 Trading Engine — SQLAlchemy Engine Factory

Manages the canonical truth database connection (SQLite v0, Postgres later).
Creates data directories on first use and exposes the migration bootstrap seam.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings

log = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _ensure_dirs(settings: Settings) -> None:
    """Create runtime data directories if they don't exist."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.coinbase_raw_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.raw_dir.mkdir(parents=True, exist_ok=True)
    settings.parquet_dir.mkdir(parents=True, exist_ok=True)
    for provider in ("jupiter", "helius", "fred", "massive", "coinbase"):
        (settings.raw_dir / provider).mkdir(parents=True, exist_ok=True)
        (settings.parquet_dir / provider).mkdir(parents=True, exist_ok=True)


def _sqlite_pragmas(dbapi_conn, connection_record):
    """Set SQLite performance pragmas on connect."""
    del connection_record
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine(settings: Settings | None = None) -> Engine:
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is not None:
        return _engine

    resolved_settings = settings or get_settings()
    _ensure_dirs(resolved_settings)

    _engine = create_engine(
        resolved_settings.db_url,
        echo=False,
        pool_pre_ping=True,
    )

    if resolved_settings.db_url.startswith("sqlite"):
        event.listen(_engine, "connect", _sqlite_pragmas)

    log.info(
        "database_engine_created",
        db_url=resolved_settings.db_url.split("///")[0] + "///***",
    )
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    engine = get_engine(settings)
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def get_session(settings: Settings | None = None) -> Session:
    """Create a new database session."""
    return get_session_factory(settings)()


def _build_alembic_config(settings: Settings) -> Config:
    """Build an Alembic config pinned to the current repo and DB URL."""
    config = Config(str(_REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_REPO_ROOT / "sql" / "migrations"))
    config.set_main_option("sqlalchemy.url", settings.db_url)
    return config


def run_migrations_to_head(settings: Settings | None = None) -> None:
    """Apply Alembic migrations to head for the canonical truth database."""
    resolved_settings = settings or get_settings()
    _ensure_dirs(resolved_settings)
    command.upgrade(_build_alembic_config(resolved_settings), "head")
    log.info("database_migrated", revision="head")


def create_all_for_tests_only(settings: Settings | None = None) -> None:
    """Create tables directly from ORM metadata for dev/test-only bootstrap."""
    from d5_trading_engine.storage.truth.models import Base

    engine = get_engine(settings)
    Base.metadata.create_all(engine)
    log.warning("database_created_from_metadata_for_tests_only", tables=len(Base.metadata.tables))


def reset_engine() -> None:
    """Reset the cached engine and session factory. Used in tests."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
