"""
D5 Trading Engine — DuckDB Analytics Mirror

DuckDB is the research / analytics warehouse.
It reads from the canonical SQLite truth surface and raw Parquet files.
It is NOT the canonical write authority.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger

log = get_logger(__name__)


class DuckDBMirror:
    """DuckDB analytics mirror for research queries.

    Reads from:
    - SQLite canonical truth (via ATTACH or copy)
    - Raw Parquet files for ad-hoc analysis

    Writes to:
    - Its own DuckDB file for materialized research views
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: duckdb.DuckDBPyConnection | None = None

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        """Get or create the DuckDB connection."""
        if self._conn is None:
            self._conn = duckdb.connect(str(self.settings.duckdb_path))
            log.info("duckdb_connected", path=str(self.settings.duckdb_path))
        return self._conn

    def sync_from_sqlite(self, table_name: str) -> int:
        """Copy a table from SQLite canonical truth into DuckDB.

        Args:
            table_name: Name of the table to sync.

        Returns:
            Number of rows copied.
        """
        sqlite_path = str(self.settings.db_path)
        self.conn.execute(f"ATTACH '{sqlite_path}' AS sqlite_db (TYPE SQLITE, READ_ONLY)")
        try:
            self.conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM sqlite_db.{table_name}")
            result = self.conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()
            row_count = result[0] if result else 0
            log.info("duckdb_sync_complete", table=table_name, rows=row_count)
            return row_count
        finally:
            self.conn.execute("DETACH sqlite_db")

    def query(self, sql: str, params: list | None = None) -> list[tuple]:
        """Execute a read query against the DuckDB analytics mirror.

        Args:
            sql: SQL query string.
            params: Optional query parameters.

        Returns:
            List of result tuples.
        """
        if params:
            return self.conn.execute(sql, params).fetchall()
        return self.conn.execute(sql).fetchall()

    def attach_parquet(self, name: str, path: str | Path) -> None:
        """Create a DuckDB view over a Parquet file or directory.

        Args:
            name: View name to create.
            path: Path to Parquet file or directory of Parquet files.
        """
        path = str(path)
        self.conn.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{path}')")
        log.info("duckdb_parquet_attached", view=name, path=path)

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
