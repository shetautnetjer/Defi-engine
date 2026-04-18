"""Add paper-practice profile, loop, and decision truth.

Revision ID: 014
Revises: 013
Create Date: 2026-04-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_practice_profile_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("active_revision_id", sa.String(length=128), nullable=True),
        sa.Column("instrument_pair", sa.String(length=32), nullable=False),
        sa.Column("context_anchors_json", sa.Text(), nullable=False),
        sa.Column("cadence_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("max_open_sessions", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("profile_id", name="uq_paper_practice_profile_v1_profile_id"),
    )
    op.create_index(
        "ix_paper_practice_profile_v1_profile_id",
        "paper_practice_profile_v1",
        ["profile_id"],
    )
    op.create_index(
        "ix_paper_practice_profile_v1_status",
        "paper_practice_profile_v1",
        ["status"],
    )
    op.create_index(
        "ix_paper_practice_profile_v1_active_revision_id",
        "paper_practice_profile_v1",
        ["active_revision_id"],
    )

    op.create_table(
        "paper_practice_profile_revision_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("revision_id", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("revision_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("mutation_source", sa.String(length=32), nullable=False),
        sa.Column("source_proposal_id", sa.String(length=128), nullable=True),
        sa.Column("source_review_id", sa.String(length=128), nullable=True),
        sa.Column("source_comparison_id", sa.String(length=128), nullable=True),
        sa.Column("applied_parameter_json", sa.Text(), nullable=False),
        sa.Column("allowed_mutation_keys_json", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["paper_practice_profile_v1.profile_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_proposal_id"],
            ["improvement_proposal_v1.proposal_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_review_id"],
            ["proposal_review_v1.review_id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_comparison_id"],
            ["proposal_comparison_v1.comparison_id"],
        ),
        sa.UniqueConstraint("revision_id", name="uq_paper_practice_profile_revision_v1_revision_id"),
        sa.UniqueConstraint(
            "profile_id",
            "revision_index",
            name="uq_paper_practice_profile_revision_v1_profile_revision",
        ),
    )
    op.create_index(
        "ix_paper_practice_profile_revision_v1_revision_id",
        "paper_practice_profile_revision_v1",
        ["revision_id"],
    )
    op.create_index(
        "ix_paper_practice_profile_revision_v1_profile_id",
        "paper_practice_profile_revision_v1",
        ["profile_id"],
    )
    op.create_index(
        "ix_paper_practice_profile_revision_v1_status",
        "paper_practice_profile_revision_v1",
        ["status"],
    )
    op.create_index(
        "ix_paper_practice_profile_revision_v1_source_proposal_id",
        "paper_practice_profile_revision_v1",
        ["source_proposal_id"],
    )
    op.create_index(
        "ix_paper_practice_profile_revision_v1_source_review_id",
        "paper_practice_profile_revision_v1",
        ["source_review_id"],
    )
    op.create_index(
        "ix_paper_practice_profile_revision_v1_source_comparison_id",
        "paper_practice_profile_revision_v1",
        ["source_comparison_id"],
    )

    op.create_table(
        "paper_practice_loop_run_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("loop_run_id", sa.String(length=128), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="running"),
        sa.Column("active_profile_id", sa.String(length=128), nullable=False),
        sa.Column("active_revision_id", sa.String(length=128), nullable=False),
        sa.Column("with_helius_ws", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_iterations", sa.Integer(), nullable=True),
        sa.Column("iterations_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latest_decision_id", sa.String(length=128), nullable=True),
        sa.Column("latest_session_key", sa.String(length=128), nullable=True),
        sa.Column("last_cycle_id", sa.String(length=128), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["active_profile_id"],
            ["paper_practice_profile_v1.profile_id"],
        ),
        sa.ForeignKeyConstraint(
            ["active_revision_id"],
            ["paper_practice_profile_revision_v1.revision_id"],
        ),
        sa.UniqueConstraint("loop_run_id", name="uq_paper_practice_loop_run_v1_loop_run_id"),
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_loop_run_id",
        "paper_practice_loop_run_v1",
        ["loop_run_id"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_mode",
        "paper_practice_loop_run_v1",
        ["mode"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_status",
        "paper_practice_loop_run_v1",
        ["status"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_active_profile_id",
        "paper_practice_loop_run_v1",
        ["active_profile_id"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_active_revision_id",
        "paper_practice_loop_run_v1",
        ["active_revision_id"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_latest_decision_id",
        "paper_practice_loop_run_v1",
        ["latest_decision_id"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_latest_session_key",
        "paper_practice_loop_run_v1",
        ["latest_session_key"],
    )
    op.create_index(
        "ix_paper_practice_loop_run_v1_last_cycle_id",
        "paper_practice_loop_run_v1",
        ["last_cycle_id"],
    )

    op.create_table(
        "paper_practice_decision_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("loop_run_id", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_revision_id", sa.String(length=128), nullable=False),
        sa.Column("decision_type", sa.String(length=32), nullable=False),
        sa.Column("session_key", sa.String(length=128), nullable=True),
        sa.Column("quote_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("condition_run_id", sa.String(length=128), nullable=True),
        sa.Column("policy_trace_id", sa.Integer(), nullable=True),
        sa.Column("risk_verdict_id", sa.Integer(), nullable=True),
        sa.Column("decision_payload_json", sa.Text(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["loop_run_id"],
            ["paper_practice_loop_run_v1.loop_run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["paper_practice_profile_v1.profile_id"],
        ),
        sa.ForeignKeyConstraint(
            ["profile_revision_id"],
            ["paper_practice_profile_revision_v1.revision_id"],
        ),
        sa.ForeignKeyConstraint(
            ["quote_snapshot_id"],
            ["quote_snapshot.id"],
        ),
        sa.UniqueConstraint("decision_id", name="uq_paper_practice_decision_v1_decision_id"),
    )
    op.create_index(
        "ix_paper_practice_decision_v1_decision_id",
        "paper_practice_decision_v1",
        ["decision_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_loop_run_id",
        "paper_practice_decision_v1",
        ["loop_run_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_profile_id",
        "paper_practice_decision_v1",
        ["profile_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_profile_revision_id",
        "paper_practice_decision_v1",
        ["profile_revision_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_decision_type",
        "paper_practice_decision_v1",
        ["decision_type"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_session_key",
        "paper_practice_decision_v1",
        ["session_key"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_quote_snapshot_id",
        "paper_practice_decision_v1",
        ["quote_snapshot_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_condition_run_id",
        "paper_practice_decision_v1",
        ["condition_run_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_policy_trace_id",
        "paper_practice_decision_v1",
        ["policy_trace_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_risk_verdict_id",
        "paper_practice_decision_v1",
        ["risk_verdict_id"],
    )
    op.create_index(
        "ix_paper_practice_decision_v1_loop_created",
        "paper_practice_decision_v1",
        ["loop_run_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("paper_practice_decision_v1")
    op.drop_table("paper_practice_loop_run_v1")
    op.drop_table("paper_practice_profile_revision_v1")
    op.drop_table("paper_practice_profile_v1")
