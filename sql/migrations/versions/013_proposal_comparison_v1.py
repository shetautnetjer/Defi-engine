"""Add proposal comparison and supersession truth.

Revision ID: 013
Revises: 012
Create Date: 2026-04-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_comparison_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("comparison_id", sa.String(length=128), nullable=False),
        sa.Column(
            "reviewer_kind",
            sa.String(length=32),
            nullable=False,
            server_default="ai_reviewer",
        ),
        sa.Column("selection_mode", sa.String(length=16), nullable=False),
        sa.Column("comparison_scope_json", sa.Text(), nullable=False),
        sa.Column("selected_proposal_id", sa.String(length=128), nullable=True),
        sa.Column("selected_review_id", sa.String(length=128), nullable=True),
        sa.Column("selected_slice_key", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["selected_proposal_id"],
            ["improvement_proposal_v1.proposal_id"],
        ),
        sa.ForeignKeyConstraint(
            ["selected_review_id"],
            ["proposal_review_v1.review_id"],
        ),
        sa.UniqueConstraint("comparison_id", name="uq_proposal_comparison_v1_comparison_id"),
    )
    op.create_index(
        "ix_proposal_comparison_v1_comparison_id",
        "proposal_comparison_v1",
        ["comparison_id"],
    )
    op.create_index(
        "ix_proposal_comparison_v1_selection_mode",
        "proposal_comparison_v1",
        ["selection_mode"],
    )
    op.create_index(
        "ix_proposal_comparison_v1_selected_proposal_id",
        "proposal_comparison_v1",
        ["selected_proposal_id"],
    )
    op.create_index(
        "ix_proposal_comparison_v1_selected_review_id",
        "proposal_comparison_v1",
        ["selected_review_id"],
    )
    op.create_index(
        "ix_proposal_comparison_v1_selected_slice_key",
        "proposal_comparison_v1",
        ["selected_slice_key"],
    )

    op.create_table(
        "proposal_comparison_item_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("comparison_id", sa.String(length=128), nullable=False),
        sa.Column("proposal_id", sa.String(length=128), nullable=False),
        sa.Column("latest_review_id", sa.String(length=128), nullable=True),
        sa.Column("proposal_kind", sa.String(length=64), nullable=False),
        sa.Column("story_class", sa.String(length=64), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("review_decision", sa.String(length=32), nullable=False),
        sa.Column("slice_key", sa.String(length=256), nullable=False),
        sa.Column("semantic_regime", sa.String(length=64), nullable=True),
        sa.Column("macro_context_state", sa.String(length=64), nullable=True),
        sa.Column("condition_run_id", sa.String(length=128), nullable=True),
        sa.Column("maturity_rank", sa.Integer(), nullable=False),
        sa.Column("decision_rank", sa.Integer(), nullable=False),
        sa.Column("regime_fit_rank", sa.Integer(), nullable=False),
        sa.Column("evidence_score", sa.Float(), nullable=False),
        sa.Column("score_breakdown_json", sa.Text(), nullable=False),
        sa.Column("selected_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("superseded_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["proposal_comparison_v1.comparison_id"],
        ),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["improvement_proposal_v1.proposal_id"],
        ),
        sa.ForeignKeyConstraint(
            ["latest_review_id"],
            ["proposal_review_v1.review_id"],
        ),
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_comparison_id",
        "proposal_comparison_item_v1",
        ["comparison_id"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_proposal_id",
        "proposal_comparison_item_v1",
        ["proposal_id"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_latest_review_id",
        "proposal_comparison_item_v1",
        ["latest_review_id"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_proposal_kind",
        "proposal_comparison_item_v1",
        ["proposal_kind"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_story_class",
        "proposal_comparison_item_v1",
        ["story_class"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_review_decision",
        "proposal_comparison_item_v1",
        ["review_decision"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_slice_key",
        "proposal_comparison_item_v1",
        ["slice_key"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_semantic_regime",
        "proposal_comparison_item_v1",
        ["semantic_regime"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_macro_context_state",
        "proposal_comparison_item_v1",
        ["macro_context_state"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_condition_run_id",
        "proposal_comparison_item_v1",
        ["condition_run_id"],
    )
    op.create_index(
        "ix_proposal_comparison_item_v1_comparison_proposal",
        "proposal_comparison_item_v1",
        ["comparison_id", "proposal_id"],
    )

    op.create_table(
        "proposal_supersession_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("supersession_id", sa.String(length=128), nullable=False),
        sa.Column("comparison_id", sa.String(length=128), nullable=False),
        sa.Column("selected_proposal_id", sa.String(length=128), nullable=False),
        sa.Column("superseded_proposal_id", sa.String(length=128), nullable=False),
        sa.Column("proposal_kind", sa.String(length=64), nullable=False),
        sa.Column("supersession_reason", sa.Text(), nullable=False),
        sa.Column("slice_key", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["comparison_id"],
            ["proposal_comparison_v1.comparison_id"],
        ),
        sa.ForeignKeyConstraint(
            ["selected_proposal_id"],
            ["improvement_proposal_v1.proposal_id"],
        ),
        sa.ForeignKeyConstraint(
            ["superseded_proposal_id"],
            ["improvement_proposal_v1.proposal_id"],
        ),
        sa.UniqueConstraint("supersession_id", name="uq_proposal_supersession_v1_id"),
        sa.UniqueConstraint(
            "comparison_id",
            "selected_proposal_id",
            "superseded_proposal_id",
            name="uq_proposal_supersession_v1_edge",
        ),
    )
    op.create_index(
        "ix_proposal_supersession_v1_supersession_id",
        "proposal_supersession_v1",
        ["supersession_id"],
    )
    op.create_index(
        "ix_proposal_supersession_v1_comparison_id",
        "proposal_supersession_v1",
        ["comparison_id"],
    )
    op.create_index(
        "ix_proposal_supersession_v1_selected_proposal_id",
        "proposal_supersession_v1",
        ["selected_proposal_id"],
    )
    op.create_index(
        "ix_proposal_supersession_v1_superseded_proposal_id",
        "proposal_supersession_v1",
        ["superseded_proposal_id"],
    )
    op.create_index(
        "ix_proposal_supersession_v1_proposal_kind",
        "proposal_supersession_v1",
        ["proposal_kind"],
    )
    op.create_index(
        "ix_proposal_supersession_v1_slice_key",
        "proposal_supersession_v1",
        ["slice_key"],
    )


def downgrade() -> None:
    op.drop_table("proposal_supersession_v1")
    op.drop_table("proposal_comparison_item_v1")
    op.drop_table("proposal_comparison_v1")
