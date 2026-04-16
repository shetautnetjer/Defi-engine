"""Add the first explicit policy global regime trace table.

Revision ID: 005
Revises: 004
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "policy_global_regime_trace_v1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "condition_run_id",
            sa.String(64),
            sa.ForeignKey("condition_scoring_run.run_id"),
            nullable=False,
        ),
        sa.Column(
            "condition_snapshot_id",
            sa.Integer,
            sa.ForeignKey("condition_global_regime_snapshot_v1.id"),
            nullable=False,
        ),
        sa.Column(
            "source_feature_run_id",
            sa.String(64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column("bucket_start_utc", sa.DateTime(), nullable=False),
        sa.Column("semantic_regime", sa.String(32), nullable=False),
        sa.Column("condition_confidence", sa.Float(), nullable=False),
        sa.Column("macro_context_state", sa.String(32), nullable=True),
        sa.Column("condition_blocked_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("condition_blocking_reason", sa.Text(), nullable=True),
        sa.Column("policy_state", sa.String(32), nullable=False),
        sa.Column("advisory_bias", sa.String(32), nullable=False),
        sa.Column("allow_new_long_hypotheses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("allow_new_short_hypotheses", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("config_status", sa.String(32), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_policy_global_regime_trace_v1_condition_run_id",
        "policy_global_regime_trace_v1",
        ["condition_run_id"],
    )
    op.create_index(
        "ix_policy_global_regime_trace_v1_condition_snapshot_id",
        "policy_global_regime_trace_v1",
        ["condition_snapshot_id"],
    )
    op.create_index(
        "ix_policy_global_regime_trace_v1_source_feature_run_id",
        "policy_global_regime_trace_v1",
        ["source_feature_run_id"],
    )
    op.create_index(
        "ix_policy_global_regime_trace_v1_bucket_start_utc",
        "policy_global_regime_trace_v1",
        ["bucket_start_utc"],
    )
    op.create_index(
        "ix_policy_global_regime_trace_v1_key",
        "policy_global_regime_trace_v1",
        ["bucket_start_utc", "policy_state"],
    )


def downgrade() -> None:
    op.drop_table("policy_global_regime_trace_v1")
