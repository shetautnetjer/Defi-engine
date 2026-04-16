"""Add the first explicit paper settlement ledger tables.

Revision ID: 007
Revises: 006
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_session",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_key", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("base_currency", sa.String(length=16), nullable=False, server_default="USDC"),
        sa.Column("quote_size_lamports", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("starting_cash_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ending_cash_usdc", sa.Float(), nullable=True),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_key", name="uq_paper_session_session_key"),
    )
    op.create_index("ix_paper_session_session_key", "paper_session", ["session_key"])
    op.create_index("ix_paper_session_status", "paper_session", ["status"])

    op.create_table(
        "paper_fill",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("paper_session.id"), nullable=False),
        sa.Column(
            "risk_verdict_id",
            sa.Integer(),
            sa.ForeignKey("risk_global_regime_gate_v1.id"),
            nullable=False,
        ),
        sa.Column(
            "policy_trace_id",
            sa.Integer(),
            sa.ForeignKey("policy_global_regime_trace_v1.id"),
            nullable=False,
        ),
        sa.Column(
            "condition_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("condition_global_regime_snapshot_v1.id"),
            nullable=False,
        ),
        sa.Column(
            "source_feature_run_id",
            sa.String(length=64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column(
            "quote_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("quote_snapshot.id"),
            nullable=False,
        ),
        sa.Column("policy_state", sa.String(length=32), nullable=False),
        sa.Column("risk_state", sa.String(length=32), nullable=False),
        sa.Column("request_direction", sa.String(length=16), nullable=False),
        sa.Column("input_mint", sa.String(length=64), nullable=False),
        sa.Column("output_mint", sa.String(length=64), nullable=False),
        sa.Column("input_amount", sa.String(length=32), nullable=False),
        sa.Column("output_amount", sa.String(length=32), nullable=False),
        sa.Column("fill_price_usdc", sa.Float(), nullable=False),
        sa.Column("price_impact_pct", sa.Float(), nullable=True),
        sa.Column("slippage_bps", sa.Integer(), nullable=True),
        sa.Column("fill_side", sa.String(length=16), nullable=False),
        sa.Column("fill_role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_paper_fill_session_id", "paper_fill", ["session_id"])
    op.create_index("ix_paper_fill_risk_verdict_id", "paper_fill", ["risk_verdict_id"])
    op.create_index("ix_paper_fill_policy_trace_id", "paper_fill", ["policy_trace_id"])
    op.create_index(
        "ix_paper_fill_condition_snapshot_id",
        "paper_fill",
        ["condition_snapshot_id"],
    )
    op.create_index(
        "ix_paper_fill_source_feature_run_id",
        "paper_fill",
        ["source_feature_run_id"],
    )
    op.create_index("ix_paper_fill_quote_snapshot_id", "paper_fill", ["quote_snapshot_id"])

    op.create_table(
        "paper_position",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("paper_session.id"), nullable=False),
        sa.Column("mint", sa.String(length=64), nullable=False),
        sa.Column("net_quantity", sa.Float(), nullable=False),
        sa.Column("cost_basis_usdc", sa.Float(), nullable=False),
        sa.Column("last_fill_id", sa.Integer(), sa.ForeignKey("paper_fill.id"), nullable=False),
        sa.Column("last_mark_source", sa.String(length=32), nullable=True),
        sa.Column(
            "last_mark_quote_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("quote_snapshot.id"),
            nullable=True,
        ),
        sa.Column("last_mark_price_usdc", sa.Float(), nullable=True),
        sa.Column("last_marked_at", sa.DateTime(), nullable=True),
        sa.Column("realized_pnl_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("unrealized_pnl_usdc", sa.Float(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("session_id", "mint", name="uq_paper_position_session_mint"),
    )
    op.create_index("ix_paper_position_session_id", "paper_position", ["session_id"])
    op.create_index("ix_paper_position_mint", "paper_position", ["mint"])
    op.create_index("ix_paper_position_last_fill_id", "paper_position", ["last_fill_id"])
    op.create_index(
        "ix_paper_position_last_mark_quote_snapshot_id",
        "paper_position",
        ["last_mark_quote_snapshot_id"],
    )

    op.create_table(
        "paper_session_report",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("paper_session.id"), nullable=False),
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
    op.create_index("ix_paper_session_report_session_id", "paper_session_report", ["session_id"])


def downgrade() -> None:
    op.drop_table("paper_session_report")
    op.drop_table("paper_position")
    op.drop_table("paper_fill")
    op.drop_table("paper_session")
