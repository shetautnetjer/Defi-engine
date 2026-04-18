"""Add artifact receipts and improvement proposal truth.

Revision ID: 011
Revises: 010
Create Date: 2026-04-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "artifact_reference",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("owner_type", sa.String(length=32), nullable=False),
        sa.Column("owner_key", sa.String(length=128), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_format", sa.String(length=16), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_artifact_reference_owner_type",
        "artifact_reference",
        ["owner_type"],
    )
    op.create_index(
        "ix_artifact_reference_owner_key",
        "artifact_reference",
        ["owner_key"],
    )
    op.create_index(
        "ix_artifact_reference_owner",
        "artifact_reference",
        ["owner_type", "owner_key"],
    )

    op.create_table(
        "improvement_proposal_v1",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("proposal_id", sa.String(length=128), nullable=False),
        sa.Column("proposal_kind", sa.String(length=64), nullable=False),
        sa.Column("source_owner_type", sa.String(length=32), nullable=False),
        sa.Column("source_owner_key", sa.String(length=128), nullable=False),
        sa.Column("governance_scope", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="proposed"),
        sa.Column(
            "runtime_effect",
            sa.String(length=32),
            nullable=False,
            server_default="advisory_only",
        ),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("next_test", sa.Text(), nullable=False),
        sa.Column("metrics_json", sa.Text(), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("proposal_id", name="uq_improvement_proposal_v1_proposal_id"),
    )
    op.create_index(
        "ix_improvement_proposal_v1_proposal_id",
        "improvement_proposal_v1",
        ["proposal_id"],
    )
    op.create_index(
        "ix_improvement_proposal_v1_proposal_kind",
        "improvement_proposal_v1",
        ["proposal_kind"],
    )
    op.create_index(
        "ix_improvement_proposal_v1_source_owner_type",
        "improvement_proposal_v1",
        ["source_owner_type"],
    )
    op.create_index(
        "ix_improvement_proposal_v1_source_owner_key",
        "improvement_proposal_v1",
        ["source_owner_key"],
    )
    op.create_index(
        "ix_improvement_proposal_v1_source_owner",
        "improvement_proposal_v1",
        ["source_owner_type", "source_owner_key"],
    )


def downgrade() -> None:
    op.drop_table("improvement_proposal_v1")
    op.drop_table("artifact_reference")
