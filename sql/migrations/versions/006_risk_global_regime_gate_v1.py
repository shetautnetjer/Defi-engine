"""Add the first explicit risk global regime gate table.

Revision ID: 006
Revises: 005
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "risk_global_regime_gate_v1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "policy_trace_id",
            sa.Integer,
            sa.ForeignKey("policy_global_regime_trace_v1.id"),
            nullable=False,
        ),
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
        sa.Column("policy_state", sa.String(32), nullable=False),
        sa.Column("risk_state", sa.String(32), nullable=False),
        sa.Column("macro_context_state", sa.String(32), nullable=True),
        sa.Column("condition_blocked_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stale_data_authorized_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unresolved_input_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "anomaly_signal_state",
            sa.String(32),
            nullable=False,
            server_default="not_owned",
        ),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_risk_global_regime_gate_v1_policy_trace_id",
        "risk_global_regime_gate_v1",
        ["policy_trace_id"],
    )
    op.create_index(
        "ix_risk_global_regime_gate_v1_condition_run_id",
        "risk_global_regime_gate_v1",
        ["condition_run_id"],
    )
    op.create_index(
        "ix_risk_global_regime_gate_v1_condition_snapshot_id",
        "risk_global_regime_gate_v1",
        ["condition_snapshot_id"],
    )
    op.create_index(
        "ix_risk_global_regime_gate_v1_source_feature_run_id",
        "risk_global_regime_gate_v1",
        ["source_feature_run_id"],
    )
    op.create_index(
        "ix_risk_global_regime_gate_v1_bucket_start_utc",
        "risk_global_regime_gate_v1",
        ["bucket_start_utc"],
    )
    op.create_index(
        "ix_risk_global_regime_gate_v1_key",
        "risk_global_regime_gate_v1",
        ["bucket_start_utc", "risk_state"],
    )


def downgrade() -> None:
    op.drop_table("risk_global_regime_gate_v1")
