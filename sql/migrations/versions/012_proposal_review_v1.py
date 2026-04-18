"""Add proposal review truth.

Revision ID: 012
Revises: 011
Create Date: 2026-04-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "proposal_review_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("proposal_id", sa.String(length=128), nullable=False),
        sa.Column("decision", sa.String(length=16), nullable=False),
        sa.Column(
            "reviewer_kind",
            sa.String(length=32),
            nullable=False,
            server_default="ai_reviewer",
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("regime_scope_json", sa.Text(), nullable=False),
        sa.Column("condition_scope_json", sa.Text(), nullable=False),
        sa.Column("recommended_next_test", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["proposal_id"],
            ["improvement_proposal_v1.proposal_id"],
        ),
        sa.UniqueConstraint("review_id", name="uq_proposal_review_v1_review_id"),
    )
    op.create_index(
        "ix_proposal_review_v1_review_id",
        "proposal_review_v1",
        ["review_id"],
    )
    op.create_index(
        "ix_proposal_review_v1_proposal_id",
        "proposal_review_v1",
        ["proposal_id"],
    )
    op.create_index(
        "ix_proposal_review_v1_decision",
        "proposal_review_v1",
        ["decision"],
    )
    op.create_index(
        "ix_proposal_review_v1_proposal_decision",
        "proposal_review_v1",
        ["proposal_id", "decision"],
    )


def downgrade() -> None:
    op.drop_table("proposal_review_v1")
