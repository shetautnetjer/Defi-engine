"""
D5 Trading Engine — CLI Entry Point

Commands:
- d5 init         : Apply Alembic migrations to head
- d5 capture      : Run data capture for one or all providers
- d5 status       : Show engine health and ingest run stats
- d5 sync-duckdb  : Sync canonical truth tables to DuckDB mirror
"""

from __future__ import annotations

import asyncio
import sys

import click

from d5_trading_engine.common.logging import get_logger, setup_logging
from d5_trading_engine.config.settings import get_settings

log = get_logger(__name__)

_CAPTURE_CHOICES = [
    "jupiter-tokens",
    "jupiter-prices",
    "jupiter-quotes",
    "helius-transactions",
    "helius-discovery",
    "helius-ws-events",
    "coinbase-products",
    "coinbase-candles",
    "coinbase-market-trades",
    "coinbase-book",
    "fred-series",
    "fred-observations",
    "massive-crypto",
    "all",
]


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """D5 Trading Engine — crypto data capture + research engine."""
    level = "DEBUG" if verbose else "INFO"
    setup_logging(level=level)


@cli.command()
def init() -> None:
    """Apply Alembic migrations to the canonical truth database."""
    from d5_trading_engine.storage.truth.engine import run_migrations_to_head

    settings = get_settings()
    click.echo(f"Applying migrations to database at {settings.db_path}")

    try:
        run_migrations_to_head(settings)
        click.echo("✓ Database migrations applied to head.")
    except Exception as exc:
        click.echo(f"✗ Database migration failed: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("provider", type=click.Choice(_CAPTURE_CHOICES, case_sensitive=False))
def capture(provider: str) -> None:
    """Run data capture for a specific provider or all."""
    from d5_trading_engine.capture.runner import CaptureRunner

    settings = get_settings()
    runner = CaptureRunner(settings)

    async def _run() -> None:
        try:
            if provider in {"jupiter-tokens", "all"}:
                run_id = await runner.capture_jupiter_tokens()
                click.echo(f"  ✓ Jupiter tokens: {run_id}")

            if provider in {"jupiter-prices", "all"}:
                run_id = await runner.capture_jupiter_prices()
                click.echo(f"  ✓ Jupiter prices: {run_id}")

            if provider in {"jupiter-quotes", "all"}:
                run_id = await runner.capture_jupiter_quotes()
                click.echo(f"  ✓ Jupiter quotes: {run_id}")

            if provider in {"helius-transactions", "all"}:
                run_id = await runner.capture_helius_transactions()
                click.echo(f"  ✓ Helius transactions: {run_id}")

            if provider in {"helius-discovery", "all"}:
                run_id = await runner.capture_helius_discovery()
                click.echo(f"  ✓ Helius discovery: {run_id}")

            if provider in {"helius-ws-events"}:
                run_id = await runner.capture_helius_ws_events()
                click.echo(f"  ✓ Helius ws events: {run_id}")

            if provider in {"coinbase-products", "all"}:
                run_id = await runner.capture_coinbase_products()
                click.echo(f"  ✓ Coinbase products: {run_id}")

            if provider in {"coinbase-candles", "all"}:
                run_id = await runner.capture_coinbase_candles()
                click.echo(f"  ✓ Coinbase candles: {run_id}")

            if provider in {"coinbase-market-trades", "all"}:
                run_id = await runner.capture_coinbase_market_trades()
                click.echo(f"  ✓ Coinbase market trades: {run_id}")

            if provider in {"coinbase-book", "all"}:
                run_id = await runner.capture_coinbase_book()
                click.echo(f"  ✓ Coinbase book: {run_id}")

            if provider in {"fred-series", "all"}:
                run_id = runner.capture_fred_series()
                click.echo(f"  ✓ FRED series: {run_id}")

            if provider in {"fred-observations", "all"}:
                run_id = runner.capture_fred_observations()
                click.echo(f"  ✓ FRED observations: {run_id}")

            if provider in {"massive-crypto", "all"}:
                run_id = await runner.capture_massive_crypto()
                click.echo(f"  ✓ Massive crypto: {run_id}")
        except Exception as exc:
            click.echo(f"  ✗ Capture failed: {exc}", err=True)
            sys.exit(1)

    click.echo(f"Starting capture: {provider}")
    asyncio.run(_run())
    click.echo("Capture complete.")


@cli.command()
def status() -> None:
    """Show engine health — recent ingest runs and source health."""
    from sqlalchemy import func

    from d5_trading_engine.storage.truth.engine import get_session
    from d5_trading_engine.storage.truth.models import IngestRun, SourceHealthEvent

    settings = get_settings()
    session = get_session(settings)

    try:
        click.echo("=== Recent Ingest Runs ===")
        runs = session.query(IngestRun).order_by(IngestRun.created_at.desc()).limit(10).all()
        if not runs:
            click.echo("  No ingest runs yet.")
        for run in runs:
            click.echo(
                f"  {run.run_id:40s}  {run.status:8s}  "
                f"records={run.records_captured or 0:5d}  "
                f"{run.started_at}"
            )

        click.echo("\n=== Source Health ===")
        subq = (
            session.query(
                SourceHealthEvent.provider,
                func.max(SourceHealthEvent.checked_at).label("latest"),
            )
            .group_by(SourceHealthEvent.provider)
            .subquery()
        )
        events = (
            session.query(SourceHealthEvent)
            .join(
                subq,
                (SourceHealthEvent.provider == subq.c.provider)
                & (SourceHealthEvent.checked_at == subq.c.latest),
            )
            .all()
        )
        if not events:
            click.echo("  No health events yet.")
        for event in events:
            indicator = "✓" if event.is_healthy else "✗"
            click.echo(
                f"  {indicator} {event.provider:10s}  "
                f"latency={event.latency_ms:.0f}ms  "
                f"{event.endpoint}  "
                f"{event.checked_at}"
            )

        click.echo(f"\nDB: {settings.db_path}")
        click.echo(f"DuckDB: {settings.duckdb_path}")
        click.echo(f"Coinbase raw DB: {settings.coinbase_raw_db_path}")
        click.echo(f"Raw data: {settings.raw_dir}")
    finally:
        session.close()


@cli.command("sync-duckdb")
@click.argument("tables", nargs=-1)
def sync_duckdb(tables: tuple[str, ...]) -> None:
    """Sync canonical truth tables to DuckDB analytics mirror."""
    from d5_trading_engine.storage.analytics.duckdb_mirror import DuckDBMirror

    default_tables = [
        "token_registry",
        "token_metadata_snapshot",
        "token_price_snapshot",
        "quote_snapshot",
        "fred_series_registry",
        "fred_observation",
        "program_registry",
        "solana_address_registry",
        "solana_transfer_event",
        "market_instrument_registry",
        "market_candle",
        "market_trade_event",
        "order_book_l2_event",
        "ingest_run",
        "source_health_event",
    ]

    tables_to_sync = list(tables) if tables else default_tables
    mirror = DuckDBMirror()

    click.echo("Syncing to DuckDB analytics mirror...")
    for table in tables_to_sync:
        try:
            rows = mirror.sync_from_sqlite(table)
            click.echo(f"  ✓ {table}: {rows} rows")
        except Exception as exc:
            click.echo(f"  ✗ {table}: {exc}", err=True)

    mirror.close()
    click.echo("DuckDB sync complete.")


def main() -> None:
    """Entry point for the d5 CLI."""
    cli()


if __name__ == "__main__":
    main()
