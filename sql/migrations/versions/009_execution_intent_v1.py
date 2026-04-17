"""Add the first explicit execution-intent owner surface.

Revision ID: 009
Revises: 008
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_intent_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("intent_key", sa.String(length=128), nullable=False),
        sa.Column(
            "risk_verdict_id",
            sa.Integer(),
            sa.ForeignKey("risk_global_regime_gate_v1.id"),
            nullable=True,
        ),
        sa.Column(
            "policy_trace_id",
            sa.Integer(),
            sa.ForeignKey("policy_global_regime_trace_v1.id"),
            nullable=True,
        ),
        sa.Column(
            "condition_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("condition_global_regime_snapshot_v1.id"),
            nullable=True,
        ),
        sa.Column(
            "source_feature_run_id",
            sa.String(length=64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=True,
        ),
        sa.Column(
            "quote_snapshot_id",
            sa.Integer(),
            sa.ForeignKey("quote_snapshot.id"),
            nullable=True,
        ),
        sa.Column("bucket_start_utc", sa.DateTime(), nullable=True),
        sa.Column("intent_state", sa.String(length=16), nullable=False),
        sa.Column("venue", sa.String(length=32), nullable=False),
        sa.Column("settlement_model", sa.String(length=32), nullable=False),
        sa.Column("strategy_family", sa.String(length=64), nullable=False),
        sa.Column("policy_state", sa.String(length=32), nullable=True),
        sa.Column("risk_state", sa.String(length=32), nullable=True),
        sa.Column("request_direction", sa.String(length=16), nullable=True),
        sa.Column("intent_side", sa.String(length=16), nullable=True),
        sa.Column("intent_role", sa.String(length=16), nullable=False, server_default="entry"),
        sa.Column("entry_intent", sa.String(length=32), nullable=False),
        sa.Column("exit_intent", sa.String(length=32), nullable=False),
        sa.Column("stop_intent", sa.String(length=32), nullable=False),
        sa.Column("input_mint", sa.String(length=64), nullable=True),
        sa.Column("output_mint", sa.String(length=64), nullable=True),
        sa.Column("quote_size_lamports", sa.Integer(), nullable=True),
        sa.Column("quoted_output_amount", sa.String(length=32), nullable=True),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("intent_key", name="uq_execution_intent_v1_intent_key"),
    )
    op.create_index("ix_execution_intent_v1_intent_key", "execution_intent_v1", ["intent_key"])
    op.create_index(
        "ix_execution_intent_v1_risk_verdict_id",
        "execution_intent_v1",
        ["risk_verdict_id"],
    )
    op.create_index(
        "ix_execution_intent_v1_policy_trace_id",
        "execution_intent_v1",
        ["policy_trace_id"],
    )
    op.create_index(
        "ix_execution_intent_v1_condition_snapshot_id",
        "execution_intent_v1",
        ["condition_snapshot_id"],
    )
    op.create_index(
        "ix_execution_intent_v1_source_feature_run_id",
        "execution_intent_v1",
        ["source_feature_run_id"],
    )
    op.create_index(
        "ix_execution_intent_v1_quote_snapshot_id",
        "execution_intent_v1",
        ["quote_snapshot_id"],
    )
    op.create_index(
        "ix_execution_intent_v1_bucket_start_utc",
        "execution_intent_v1",
        ["bucket_start_utc"],
    )
    op.create_index(
        "ix_execution_intent_v1_intent_state",
        "execution_intent_v1",
        ["intent_state"],
    )
    op.create_index(
        "ix_execution_intent_v1_risk_state",
        "execution_intent_v1",
        ["intent_state", "risk_state"],
    )

    with op.batch_alter_table("paper_fill") as batch_op:
        batch_op.add_column(
            sa.Column("execution_intent_id", sa.Integer(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_paper_fill_execution_intent_v1",
            "execution_intent_v1",
            ["execution_intent_id"],
            ["id"],
        )
        batch_op.create_index(
            "ix_paper_fill_execution_intent_id",
            ["execution_intent_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("paper_fill") as batch_op:
        batch_op.drop_index("ix_paper_fill_execution_intent_id")
        batch_op.drop_constraint("fk_paper_fill_execution_intent_v1", type_="foreignkey")
        batch_op.drop_column("execution_intent_id")
    op.drop_table("execution_intent_v1")
