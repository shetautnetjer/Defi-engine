from __future__ import annotations

from sqlalchemy import create_engine, inspect

from d5_trading_engine.storage.truth.engine import (
    create_all_for_tests_only,
    run_migrations_to_head,
)
from d5_trading_engine.storage.truth.models import Base


def test_run_migrations_to_head_creates_modeled_tables(settings) -> None:
    run_migrations_to_head(settings)

    inspector = inspect(create_engine(settings.db_url))
    actual_tables = set(inspector.get_table_names())

    assert "alembic_version" in actual_tables
    assert set(Base.metadata.tables).issubset(actual_tables)


def test_run_migrations_to_head_is_idempotent(settings) -> None:
    run_migrations_to_head(settings)
    run_migrations_to_head(settings)

    inspector = inspect(create_engine(settings.db_url))
    assert "alembic_version" in set(inspector.get_table_names())


def test_create_all_for_tests_only_stays_non_authoritative(settings) -> None:
    create_all_for_tests_only(settings)

    inspector = inspect(create_engine(settings.db_url))
    actual_tables = set(inspector.get_table_names())

    assert set(Base.metadata.tables).issubset(actual_tables)
    assert "alembic_version" not in actual_tables
