"""Add advisory realized-feedback comparison receipts for shadow experiments.

Revision ID: 008
Revises: 007
Create Date: 2026-04-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "experiment_realized_feedback_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "experiment_run_id",
            sa.String(length=64),
            sa.ForeignKey("experiment_run.run_id"),
            nullable=False,
        ),
        sa.Column(
            "paper_fill_id",
            sa.Integer(),
            sa.ForeignKey("paper_fill.id"),
            nullable=False,
        ),
        sa.Column(
            "paper_session_id",
            sa.Integer(),
            sa.ForeignKey("paper_session.id"),
            nullable=False,
        ),
        sa.Column(
            "paper_position_id",
            sa.Integer(),
            sa.ForeignKey("paper_position.id"),
            nullable=True,
        ),
        sa.Column(
            "paper_session_report_id",
            sa.Integer(),
            sa.ForeignKey("paper_session_report.id"),
            nullable=True,
        ),
        sa.Column(
            "source_feature_run_id",
            sa.String(length=64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column("matched_mint", sa.String(length=64), nullable=False),
        sa.Column("matched_bucket_15m_utc", sa.DateTime(), nullable=True),
        sa.Column("matched_bucket_5m_utc", sa.DateTime(), nullable=True),
        sa.Column("comparison_state", sa.String(length=16), nullable=False),
        sa.Column("match_method", sa.String(length=128), nullable=False),
        sa.Column("match_tolerance_seconds", sa.Integer(), nullable=False),
        sa.Column("shadow_context_json", sa.Text(), nullable=False),
        sa.Column("realized_outcome_json", sa.Text(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "experiment_run_id",
            "paper_fill_id",
            name="uq_experiment_realized_feedback_run_fill",
        ),
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_experiment_run_id",
        "experiment_realized_feedback_v1",
        ["experiment_run_id"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_paper_fill_id",
        "experiment_realized_feedback_v1",
        ["paper_fill_id"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_paper_session_id",
        "experiment_realized_feedback_v1",
        ["paper_session_id"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_paper_position_id",
        "experiment_realized_feedback_v1",
        ["paper_position_id"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_paper_session_report_id",
        "experiment_realized_feedback_v1",
        ["paper_session_report_id"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_source_feature_run_id",
        "experiment_realized_feedback_v1",
        ["source_feature_run_id"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_matched_mint",
        "experiment_realized_feedback_v1",
        ["matched_mint"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_matched_bucket_15m_utc",
        "experiment_realized_feedback_v1",
        ["matched_bucket_15m_utc"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_matched_bucket_5m_utc",
        "experiment_realized_feedback_v1",
        ["matched_bucket_5m_utc"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_v1_comparison_state",
        "experiment_realized_feedback_v1",
        ["comparison_state"],
    )
    op.create_index(
        "ix_experiment_realized_feedback_run_state",
        "experiment_realized_feedback_v1",
        ["experiment_run_id", "comparison_state"],
    )


def downgrade() -> None:
    op.drop_table("experiment_realized_feedback_v1")
