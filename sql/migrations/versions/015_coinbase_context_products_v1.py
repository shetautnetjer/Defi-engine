"""Add Coinbase derivative metadata columns to market instrument registry.

Revision ID: 015
Revises: 014
Create Date: 2026-04-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "market_instrument_registry",
        sa.Column("product_venue", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "market_instrument_registry",
        sa.Column("contract_expiry_type", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "market_instrument_registry",
        sa.Column("futures_asset_type", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "market_instrument_registry",
        sa.Column("contract_root_unit", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("market_instrument_registry", "contract_root_unit")
    op.drop_column("market_instrument_registry", "futures_asset_type")
    op.drop_column("market_instrument_registry", "contract_expiry_type")
    op.drop_column("market_instrument_registry", "product_venue")
