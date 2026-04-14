"""Add the first bounded feature materialization table.

Revision ID: 003
Revises: 002
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "feature_materialization_run",
        sa.Column("freshness_snapshot_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "feature_materialization_run",
        sa.Column("input_window_start_utc", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "feature_materialization_run",
        sa.Column("input_window_end_utc", sa.DateTime(), nullable=True),
    )
    op.create_table(
        "feature_spot_chain_macro_minute_v1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "feature_run_id",
            sa.String(64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column("feature_minute_utc", sa.DateTime, nullable=False),
        sa.Column("mint", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("coinbase_product_id", sa.String(64), nullable=True),
        sa.Column("jupiter_price_usd", sa.Float, nullable=True),
        sa.Column("quote_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("mean_quote_price_impact_pct", sa.Float, nullable=True),
        sa.Column("mean_quote_response_latency_ms", sa.Float, nullable=True),
        sa.Column("coinbase_close", sa.Float, nullable=True),
        sa.Column("coinbase_trade_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("coinbase_trade_size_sum", sa.Float, nullable=True),
        sa.Column("coinbase_book_spread_bps", sa.Float, nullable=True),
        sa.Column("chain_transfer_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("chain_amount_in", sa.Float, nullable=True),
        sa.Column("chain_amount_out", sa.Float, nullable=True),
        sa.Column("fred_dff", sa.Float, nullable=True),
        sa.Column("fred_t10y2y", sa.Float, nullable=True),
        sa.Column("fred_vixcls", sa.Float, nullable=True),
        sa.Column("fred_dgs10", sa.Float, nullable=True),
        sa.Column("fred_dtwexbgs", sa.Float, nullable=True),
        sa.Column("event_date_utc", sa.String(10), nullable=True),
        sa.Column("hour_utc", sa.Integer, nullable=True),
        sa.Column("minute_of_day_utc", sa.Integer, nullable=True),
        sa.Column("weekday_utc", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_feature_spot_chain_macro_minute_v1_feature_run_id",
        "feature_spot_chain_macro_minute_v1",
        ["feature_run_id"],
    )
    op.create_index(
        "ix_feature_spot_chain_macro_minute_v1_feature_minute_utc",
        "feature_spot_chain_macro_minute_v1",
        ["feature_minute_utc"],
    )
    op.create_index(
        "ix_feature_spot_chain_macro_minute_v1_mint",
        "feature_spot_chain_macro_minute_v1",
        ["mint"],
    )
    op.create_index(
        "ix_feature_spot_chain_macro_minute_v1_symbol",
        "feature_spot_chain_macro_minute_v1",
        ["symbol"],
    )
    op.create_index(
        "ix_feature_spot_chain_macro_minute_v1_coinbase_product_id",
        "feature_spot_chain_macro_minute_v1",
        ["coinbase_product_id"],
    )
    op.create_index(
        "ix_feature_spot_chain_macro_minute_key",
        "feature_spot_chain_macro_minute_v1",
        ["mint", "feature_minute_utc"],
    )


def downgrade() -> None:
    op.drop_table("feature_spot_chain_macro_minute_v1")
    op.drop_column("feature_materialization_run", "input_window_end_utc")
    op.drop_column("feature_materialization_run", "input_window_start_utc")
    op.drop_column("feature_materialization_run", "freshness_snapshot_json")
