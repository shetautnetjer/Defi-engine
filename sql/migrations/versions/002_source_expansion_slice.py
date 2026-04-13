"""Source expansion slice for event-time aware quotes and new market tables.

Revision ID: 002
Revises: 001
Create Date: 2026-04-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "raw_jupiter_quote_response",
        sa.Column("request_direction", sa.String(16), nullable=True),
    )
    op.add_column(
        "raw_jupiter_quote_response",
        sa.Column("requested_at", sa.DateTime, nullable=True),
    )
    op.add_column(
        "raw_jupiter_quote_response",
        sa.Column("response_latency_ms", sa.Float, nullable=True),
    )
    op.add_column(
        "raw_jupiter_quote_response",
        sa.Column("source_event_time_utc", sa.DateTime, nullable=True),
    )
    op.add_column(
        "raw_jupiter_quote_response",
        sa.Column("source_time_raw", sa.Text, nullable=True),
    )

    op.add_column(
        "quote_snapshot",
        sa.Column("request_direction", sa.String(16), nullable=True),
    )
    op.add_column("quote_snapshot", sa.Column("requested_at", sa.DateTime, nullable=True))
    op.add_column("quote_snapshot", sa.Column("response_latency_ms", sa.Float, nullable=True))
    op.add_column("quote_snapshot", sa.Column("source_event_time_utc", sa.DateTime, nullable=True))
    op.add_column("quote_snapshot", sa.Column("source_time_raw", sa.Text, nullable=True))
    op.add_column("quote_snapshot", sa.Column("event_date_utc", sa.String(10), nullable=True))
    op.add_column("quote_snapshot", sa.Column("hour_utc", sa.Integer, nullable=True))
    op.add_column("quote_snapshot", sa.Column("minute_of_day_utc", sa.Integer, nullable=True))
    op.add_column("quote_snapshot", sa.Column("weekday_utc", sa.Integer, nullable=True))
    op.add_column("quote_snapshot", sa.Column("time_quality", sa.String(16), nullable=True))
    op.create_index(
        "ix_quote_snapshot_source_event_time_utc",
        "quote_snapshot",
        ["source_event_time_utc"],
    )

    op.create_table(
        "raw_helius_account_discovery",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "ingest_run_id",
            sa.String(64),
            sa.ForeignKey("ingest_run.run_id"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="helius"),
        sa.Column("address", sa.String(64), nullable=False),
        sa.Column("owner_program_id", sa.String(64), nullable=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_raw_helius_account_discovery_ingest_run_id",
        "raw_helius_account_discovery",
        ["ingest_run_id"],
    )
    op.create_index(
        "ix_raw_helius_account_discovery_address",
        "raw_helius_account_discovery",
        ["address"],
    )
    op.create_index(
        "ix_raw_helius_account_discovery_owner_program_id",
        "raw_helius_account_discovery",
        ["owner_program_id"],
    )
    op.create_index(
        "ix_raw_helius_account_discovery_captured_at",
        "raw_helius_account_discovery",
        ["captured_at"],
    )

    op.create_table(
        "solana_transfer_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "ingest_run_id",
            sa.String(64),
            sa.ForeignKey("ingest_run.run_id"),
            nullable=False,
        ),
        sa.Column("signature", sa.String(128), nullable=True),
        sa.Column("slot", sa.Integer, nullable=True),
        sa.Column("mint", sa.String(64), nullable=True),
        sa.Column("source_address", sa.String(64), nullable=True),
        sa.Column("destination_address", sa.String(64), nullable=True),
        sa.Column("amount_raw", sa.String(64), nullable=True),
        sa.Column("amount_float", sa.Float, nullable=True),
        sa.Column("decimals", sa.Integer, nullable=True),
        sa.Column("program_id", sa.String(64), nullable=True),
        sa.Column("fee_lamports", sa.Integer, nullable=True),
        sa.Column("transfer_type", sa.String(16), nullable=False, server_default="token"),
        sa.Column("source_event_time_utc", sa.DateTime, nullable=True),
        sa.Column("captured_at_utc", sa.DateTime, nullable=False),
        sa.Column("source_time_raw", sa.Text, nullable=True),
        sa.Column("event_date_utc", sa.String(10), nullable=True),
        sa.Column("hour_utc", sa.Integer, nullable=True),
        sa.Column("minute_of_day_utc", sa.Integer, nullable=True),
        sa.Column("weekday_utc", sa.Integer, nullable=True),
        sa.Column("time_quality", sa.String(16), nullable=True),
    )
    op.create_index(
        "ix_solana_transfer_event_ingest_run_id",
        "solana_transfer_event",
        ["ingest_run_id"],
    )
    op.create_index(
        "ix_solana_transfer_event_signature",
        "solana_transfer_event",
        ["signature"],
    )
    op.create_index("ix_solana_transfer_event_slot", "solana_transfer_event", ["slot"])
    op.create_index("ix_solana_transfer_event_mint", "solana_transfer_event", ["mint"])
    op.create_index(
        "ix_solana_transfer_event_source_address",
        "solana_transfer_event",
        ["source_address"],
    )
    op.create_index(
        "ix_solana_transfer_event_destination_address",
        "solana_transfer_event",
        ["destination_address"],
    )
    op.create_index("ix_solana_transfer_event_program_id", "solana_transfer_event", ["program_id"])
    op.create_index(
        "ix_solana_transfer_event_source_event_time_utc",
        "solana_transfer_event",
        ["source_event_time_utc"],
    )
    op.create_index(
        "ix_solana_transfer_signature_time",
        "solana_transfer_event",
        ["signature", "source_event_time_utc"],
    )
    op.create_index(
        "ix_solana_transfer_event_captured_at_utc",
        "solana_transfer_event",
        ["captured_at_utc"],
    )

    op.create_table(
        "market_instrument_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("base_symbol", sa.String(32), nullable=True),
        sa.Column("quote_symbol", sa.String(32), nullable=True),
        sa.Column("product_type", sa.String(32), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("price_increment", sa.String(32), nullable=True),
        sa.Column("base_increment", sa.String(32), nullable=True),
        sa.Column("quote_increment", sa.String(32), nullable=True),
        sa.Column("first_seen_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("venue", "product_id", name="uq_market_instrument"),
    )
    op.create_index(
        "ix_market_instrument_registry_venue",
        "market_instrument_registry",
        ["venue"],
    )
    op.create_index(
        "ix_market_instrument_registry_product_id",
        "market_instrument_registry",
        ["product_id"],
    )
    op.create_index(
        "ix_market_instrument_registry_base_symbol",
        "market_instrument_registry",
        ["base_symbol"],
    )
    op.create_index(
        "ix_market_instrument_registry_quote_symbol",
        "market_instrument_registry",
        ["quote_symbol"],
    )

    op.create_table(
        "market_candle",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "ingest_run_id",
            sa.String(64),
            sa.ForeignKey("ingest_run.run_id"),
            nullable=False,
        ),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("granularity", sa.String(32), nullable=False),
        sa.Column("start_time_utc", sa.DateTime, nullable=False),
        sa.Column("end_time_utc", sa.DateTime, nullable=True),
        sa.Column("open", sa.Float, nullable=True),
        sa.Column("high", sa.Float, nullable=True),
        sa.Column("low", sa.Float, nullable=True),
        sa.Column("close", sa.Float, nullable=True),
        sa.Column("volume", sa.Float, nullable=True),
        sa.Column("source_event_time_utc", sa.DateTime, nullable=True),
        sa.Column("captured_at_utc", sa.DateTime, nullable=False),
        sa.Column("source_time_raw", sa.Text, nullable=True),
        sa.Column("event_date_utc", sa.String(10), nullable=True),
        sa.Column("hour_utc", sa.Integer, nullable=True),
        sa.Column("minute_of_day_utc", sa.Integer, nullable=True),
        sa.Column("weekday_utc", sa.Integer, nullable=True),
        sa.Column("time_quality", sa.String(16), nullable=True),
    )
    op.create_index("ix_market_candle_ingest_run_id", "market_candle", ["ingest_run_id"])
    op.create_index("ix_market_candle_venue", "market_candle", ["venue"])
    op.create_index("ix_market_candle_product_id", "market_candle", ["product_id"])
    op.create_index("ix_market_candle_start_time_utc", "market_candle", ["start_time_utc"])
    op.create_index(
        "ix_market_candle_source_event_time_utc",
        "market_candle",
        ["source_event_time_utc"],
    )
    op.create_index(
        "ix_market_candle_key",
        "market_candle",
        ["venue", "product_id", "granularity", "start_time_utc"],
    )

    op.create_table(
        "market_trade_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "ingest_run_id",
            sa.String(64),
            sa.ForeignKey("ingest_run.run_id"),
            nullable=False,
        ),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("trade_id", sa.String(128), nullable=True),
        sa.Column("side", sa.String(16), nullable=True),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("size", sa.Float, nullable=True),
        sa.Column("source_event_time_utc", sa.DateTime, nullable=True),
        sa.Column("captured_at_utc", sa.DateTime, nullable=False),
        sa.Column("source_time_raw", sa.Text, nullable=True),
        sa.Column("event_date_utc", sa.String(10), nullable=True),
        sa.Column("hour_utc", sa.Integer, nullable=True),
        sa.Column("minute_of_day_utc", sa.Integer, nullable=True),
        sa.Column("weekday_utc", sa.Integer, nullable=True),
        sa.Column("time_quality", sa.String(16), nullable=True),
    )
    op.create_index("ix_market_trade_event_ingest_run_id", "market_trade_event", ["ingest_run_id"])
    op.create_index("ix_market_trade_event_venue", "market_trade_event", ["venue"])
    op.create_index("ix_market_trade_event_product_id", "market_trade_event", ["product_id"])
    op.create_index("ix_market_trade_event_trade_id", "market_trade_event", ["trade_id"])
    op.create_index(
        "ix_market_trade_event_source_event_time_utc",
        "market_trade_event",
        ["source_event_time_utc"],
    )
    op.create_index(
        "ix_market_trade_key",
        "market_trade_event",
        ["venue", "product_id", "source_event_time_utc"],
    )

    op.create_table(
        "order_book_l2_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "ingest_run_id",
            sa.String(64),
            sa.ForeignKey("ingest_run.run_id"),
            nullable=False,
        ),
        sa.Column("venue", sa.String(32), nullable=False),
        sa.Column("product_id", sa.String(64), nullable=False),
        sa.Column("event_kind", sa.String(16), nullable=False, server_default="snapshot"),
        sa.Column("best_bid", sa.Float, nullable=True),
        sa.Column("best_ask", sa.Float, nullable=True),
        sa.Column("spread_absolute", sa.Float, nullable=True),
        sa.Column("spread_bps", sa.Float, nullable=True),
        sa.Column("bids_json", sa.Text, nullable=True),
        sa.Column("asks_json", sa.Text, nullable=True),
        sa.Column("source_event_time_utc", sa.DateTime, nullable=True),
        sa.Column("captured_at_utc", sa.DateTime, nullable=False),
        sa.Column("source_time_raw", sa.Text, nullable=True),
        sa.Column("event_date_utc", sa.String(10), nullable=True),
        sa.Column("hour_utc", sa.Integer, nullable=True),
        sa.Column("minute_of_day_utc", sa.Integer, nullable=True),
        sa.Column("weekday_utc", sa.Integer, nullable=True),
        sa.Column("time_quality", sa.String(16), nullable=True),
    )
    op.create_index(
        "ix_order_book_l2_event_ingest_run_id",
        "order_book_l2_event",
        ["ingest_run_id"],
    )
    op.create_index("ix_order_book_l2_event_venue", "order_book_l2_event", ["venue"])
    op.create_index(
        "ix_order_book_l2_event_product_id",
        "order_book_l2_event",
        ["product_id"],
    )
    op.create_index(
        "ix_order_book_l2_event_source_event_time_utc",
        "order_book_l2_event",
        ["source_event_time_utc"],
    )
    op.create_index(
        "ix_order_book_key",
        "order_book_l2_event",
        ["venue", "product_id", "source_event_time_utc"],
    )


def downgrade() -> None:
    op.drop_index("ix_order_book_key", table_name="order_book_l2_event")
    op.drop_index(
        "ix_order_book_l2_event_source_event_time_utc",
        table_name="order_book_l2_event",
    )
    op.drop_index("ix_order_book_l2_event_product_id", table_name="order_book_l2_event")
    op.drop_index("ix_order_book_l2_event_venue", table_name="order_book_l2_event")
    op.drop_index("ix_order_book_l2_event_ingest_run_id", table_name="order_book_l2_event")
    op.drop_table("order_book_l2_event")

    op.drop_index("ix_market_trade_key", table_name="market_trade_event")
    op.drop_index(
        "ix_market_trade_event_source_event_time_utc",
        table_name="market_trade_event",
    )
    op.drop_index("ix_market_trade_event_trade_id", table_name="market_trade_event")
    op.drop_index("ix_market_trade_event_product_id", table_name="market_trade_event")
    op.drop_index("ix_market_trade_event_venue", table_name="market_trade_event")
    op.drop_index("ix_market_trade_event_ingest_run_id", table_name="market_trade_event")
    op.drop_table("market_trade_event")

    op.drop_index("ix_market_candle_key", table_name="market_candle")
    op.drop_index(
        "ix_market_candle_source_event_time_utc",
        table_name="market_candle",
    )
    op.drop_index("ix_market_candle_start_time_utc", table_name="market_candle")
    op.drop_index("ix_market_candle_product_id", table_name="market_candle")
    op.drop_index("ix_market_candle_venue", table_name="market_candle")
    op.drop_index("ix_market_candle_ingest_run_id", table_name="market_candle")
    op.drop_table("market_candle")

    op.drop_index(
        "ix_market_instrument_registry_quote_symbol",
        table_name="market_instrument_registry",
    )
    op.drop_index(
        "ix_market_instrument_registry_base_symbol",
        table_name="market_instrument_registry",
    )
    op.drop_index(
        "ix_market_instrument_registry_product_id",
        table_name="market_instrument_registry",
    )
    op.drop_index(
        "ix_market_instrument_registry_venue",
        table_name="market_instrument_registry",
    )
    op.drop_table("market_instrument_registry")

    op.drop_index(
        "ix_solana_transfer_event_captured_at_utc",
        table_name="solana_transfer_event",
    )
    op.drop_index("ix_solana_transfer_signature_time", table_name="solana_transfer_event")
    op.drop_index(
        "ix_solana_transfer_event_source_event_time_utc",
        table_name="solana_transfer_event",
    )
    op.drop_index("ix_solana_transfer_event_program_id", table_name="solana_transfer_event")
    op.drop_index(
        "ix_solana_transfer_event_destination_address",
        table_name="solana_transfer_event",
    )
    op.drop_index(
        "ix_solana_transfer_event_source_address",
        table_name="solana_transfer_event",
    )
    op.drop_index("ix_solana_transfer_event_mint", table_name="solana_transfer_event")
    op.drop_index("ix_solana_transfer_event_slot", table_name="solana_transfer_event")
    op.drop_index("ix_solana_transfer_event_signature", table_name="solana_transfer_event")
    op.drop_index("ix_solana_transfer_event_ingest_run_id", table_name="solana_transfer_event")
    op.drop_table("solana_transfer_event")

    op.drop_index(
        "ix_raw_helius_account_discovery_captured_at",
        table_name="raw_helius_account_discovery",
    )
    op.drop_index(
        "ix_raw_helius_account_discovery_owner_program_id",
        table_name="raw_helius_account_discovery",
    )
    op.drop_index(
        "ix_raw_helius_account_discovery_address",
        table_name="raw_helius_account_discovery",
    )
    op.drop_index(
        "ix_raw_helius_account_discovery_ingest_run_id",
        table_name="raw_helius_account_discovery",
    )
    op.drop_table("raw_helius_account_discovery")

    op.drop_index("ix_quote_snapshot_source_event_time_utc", table_name="quote_snapshot")
    op.drop_column("quote_snapshot", "time_quality")
    op.drop_column("quote_snapshot", "weekday_utc")
    op.drop_column("quote_snapshot", "minute_of_day_utc")
    op.drop_column("quote_snapshot", "hour_utc")
    op.drop_column("quote_snapshot", "event_date_utc")
    op.drop_column("quote_snapshot", "source_time_raw")
    op.drop_column("quote_snapshot", "source_event_time_utc")
    op.drop_column("quote_snapshot", "response_latency_ms")
    op.drop_column("quote_snapshot", "requested_at")
    op.drop_column("quote_snapshot", "request_direction")

    op.drop_column("raw_jupiter_quote_response", "source_time_raw")
    op.drop_column("raw_jupiter_quote_response", "source_event_time_utc")
    op.drop_column("raw_jupiter_quote_response", "response_latency_ms")
    op.drop_column("raw_jupiter_quote_response", "requested_at")
    op.drop_column("raw_jupiter_quote_response", "request_direction")
