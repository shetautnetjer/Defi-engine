"""Separate raw SQLite store for Coinbase market-data capture."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.coinbase_raw.models import Base

log = get_logger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _ensure_dirs(settings: Settings) -> None:
    settings.coinbase_raw_db_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine(settings: Settings | None = None) -> Engine:
    """Get or create the Coinbase raw SQLite engine."""
    global _engine
    if _engine is not None:
        return _engine

    if settings is None:
        settings = get_settings()

    _ensure_dirs(settings)
    _engine = create_engine(f"sqlite:///{settings.coinbase_raw_db_path}", echo=False)
    log.info("coinbase_raw_engine_created", path=str(settings.coinbase_raw_db_path))
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Get or create the Coinbase raw session factory."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    _session_factory = sessionmaker(bind=get_engine(settings), expire_on_commit=False)
    return _session_factory


def get_session(settings: Settings | None = None) -> Session:
    """Create a new Coinbase raw DB session."""
    return get_session_factory(settings)()


def initialize(settings: Settings | None = None) -> None:
    """Ensure the Coinbase raw DB exists with its raw tables."""
    if settings is None:
        settings = get_settings()
    Base.metadata.create_all(get_engine(settings))
    log.info("coinbase_raw_initialized", tables=len(Base.metadata.tables))


def reset_engine() -> None:
    """Reset cached Coinbase raw engine state. Used in tests."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
