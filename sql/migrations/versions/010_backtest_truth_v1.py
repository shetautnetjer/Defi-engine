"""Add the first explicit backtest truth ledger tables.

Revision ID: 010
Revises: 009
Create Date: 2026-04-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str | None = "009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_session_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "instrument_family",
            sa.String(length=16),
            nullable=False,
            server_default="spot",
        ),
        sa.Column("venue", sa.String(length=32), nullable=False),
        sa.Column(
            "base_currency",
            sa.String(length=16),
            nullable=False,
            server_default="USDC",
        ),
        sa.Column("bucket_granularity", sa.String(length=16), nullable=False),
        sa.Column("fee_bps", sa.Integer(), nullable=False),
        sa.Column("slippage_bps", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("mark_method", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("starting_cash_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ending_cash_usdc", sa.Float(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_key", name="uq_backtest_session_v1_session_key"),
    )
    op.create_index(
        "ix_backtest_session_v1_session_key",
        "backtest_session_v1",
        ["session_key"],
    )
    op.create_index(
        "ix_backtest_session_v1_status",
        "backtest_session_v1",
        ["status"],
    )

    op.create_table(
        "backtest_fill_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("backtest_session_v1.id"),
            nullable=False,
        ),
        sa.Column("event_time", sa.DateTime(), nullable=False),
        sa.Column("replay_reference", sa.String(length=128), nullable=False),
        sa.Column("mint", sa.String(length=64), nullable=False),
        sa.Column("side", sa.String(length=16), nullable=False),
        sa.Column("input_amount", sa.String(length=32), nullable=False),
        sa.Column("output_amount", sa.String(length=32), nullable=False),
        sa.Column("fill_price_usdc", sa.Float(), nullable=False),
        sa.Column("fee_bps", sa.Integer(), nullable=False),
        sa.Column("fee_usdc", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_backtest_fill_v1_session_id", "backtest_fill_v1", ["session_id"])
    op.create_index("ix_backtest_fill_v1_event_time", "backtest_fill_v1", ["event_time"])
    op.create_index("ix_backtest_fill_v1_mint", "backtest_fill_v1", ["mint"])

    op.create_table(
        "backtest_position_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("backtest_session_v1.id"),
            nullable=False,
        ),
        sa.Column("mint", sa.String(length=64), nullable=False),
        sa.Column("net_quantity", sa.Float(), nullable=False),
        sa.Column("cost_basis_usdc", sa.Float(), nullable=False),
        sa.Column(
            "last_fill_id",
            sa.Integer(),
            sa.ForeignKey("backtest_fill_v1.id"),
            nullable=False,
        ),
        sa.Column("last_mark_source", sa.String(length=32), nullable=True),
        sa.Column("last_mark_reference", sa.String(length=128), nullable=True),
        sa.Column("last_mark_price_usdc", sa.Float(), nullable=True),
        sa.Column("last_marked_at", sa.DateTime(), nullable=True),
        sa.Column("realized_pnl_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "mint", name="uq_backtest_position_session_mint"),
    )
    op.create_index(
        "ix_backtest_position_v1_session_id",
        "backtest_position_v1",
        ["session_id"],
    )
    op.create_index("ix_backtest_position_v1_mint", "backtest_position_v1", ["mint"])
    op.create_index(
        "ix_backtest_position_v1_last_fill_id",
        "backtest_position_v1",
        ["last_fill_id"],
    )

    op.create_table(
        "backtest_session_report_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("backtest_session_v1.id"),
            nullable=False,
        ),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("cash_usdc", sa.Float(), nullable=False),
        sa.Column("position_value_usdc", sa.Float(), nullable=False),
        sa.Column("equity_usdc", sa.Float(), nullable=False),
        sa.Column("realized_pnl_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mark_method", sa.String(length=32), nullable=False),
        sa.Column("mark_inputs_json", sa.Text(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_backtest_session_report_v1_session_id",
        "backtest_session_report_v1",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_table("backtest_session_report_v1")
    op.drop_table("backtest_position_v1")
    op.drop_table("backtest_fill_v1")
    op.drop_table("backtest_session_v1")
