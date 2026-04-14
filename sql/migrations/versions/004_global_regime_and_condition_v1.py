"""Add global regime inputs and condition scoring truth tables.

Revision ID: 004
Revises: 003
Create Date: 2026-04-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "feature_global_regime_input_15m_v1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "feature_run_id",
            sa.String(64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column("bucket_start_utc", sa.DateTime(), nullable=False),
        sa.Column("regime_key", sa.String(32), nullable=False, server_default="global"),
        sa.Column("proxy_products_json", sa.Text(), nullable=True),
        sa.Column("proxy_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("market_return_mean_15m", sa.Float(), nullable=True),
        sa.Column("market_return_std_15m", sa.Float(), nullable=True),
        sa.Column("market_realized_vol_15m", sa.Float(), nullable=True),
        sa.Column("market_volume_sum_15m", sa.Float(), nullable=True),
        sa.Column("market_trade_count_15m", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("market_trade_size_sum_15m", sa.Float(), nullable=True),
        sa.Column("market_book_spread_bps_mean_15m", sa.Float(), nullable=True),
        sa.Column("market_return_mean_4h", sa.Float(), nullable=True),
        sa.Column("market_realized_vol_4h", sa.Float(), nullable=True),
        sa.Column("macro_context_available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fred_dff", sa.Float(), nullable=True),
        sa.Column("fred_t10y2y", sa.Float(), nullable=True),
        sa.Column("fred_vixcls", sa.Float(), nullable=True),
        sa.Column("fred_dgs10", sa.Float(), nullable=True),
        sa.Column("fred_dtwexbgs", sa.Float(), nullable=True),
        sa.Column("event_date_utc", sa.String(10), nullable=True),
        sa.Column("hour_utc", sa.Integer(), nullable=True),
        sa.Column("minute_of_day_utc", sa.Integer(), nullable=True),
        sa.Column("weekday_utc", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_feature_global_regime_input_15m_v1_feature_run_id",
        "feature_global_regime_input_15m_v1",
        ["feature_run_id"],
    )
    op.create_index(
        "ix_feature_global_regime_input_15m_v1_bucket_start_utc",
        "feature_global_regime_input_15m_v1",
        ["bucket_start_utc"],
    )
    op.create_index(
        "ix_feature_global_regime_input_15m_key",
        "feature_global_regime_input_15m_v1",
        ["regime_key", "bucket_start_utc"],
    )
    op.create_table(
        "condition_scoring_run",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("condition_set", sa.String(128), nullable=False),
        sa.Column(
            "source_feature_run_id",
            sa.String(64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column("model_family", sa.String(64), nullable=False),
        sa.Column("training_window_start_utc", sa.DateTime(), nullable=True),
        sa.Column("training_window_end_utc", sa.DateTime(), nullable=True),
        sa.Column("scored_bucket_start_utc", sa.DateTime(), nullable=True),
        sa.Column("state_semantics_json", sa.Text(), nullable=True),
        sa.Column("model_params_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("run_id", name="uq_condition_scoring_run_run_id"),
    )
    op.create_index(
        "ix_condition_scoring_run_run_id",
        "condition_scoring_run",
        ["run_id"],
        unique=True,
    )
    op.create_index(
        "ix_condition_scoring_run_source_feature_run_id",
        "condition_scoring_run",
        ["source_feature_run_id"],
    )
    op.create_table(
        "condition_global_regime_snapshot_v1",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "condition_run_id",
            sa.String(64),
            sa.ForeignKey("condition_scoring_run.run_id"),
            nullable=False,
        ),
        sa.Column(
            "source_feature_run_id",
            sa.String(64),
            sa.ForeignKey("feature_materialization_run.run_id"),
            nullable=False,
        ),
        sa.Column("bucket_start_utc", sa.DateTime(), nullable=False),
        sa.Column("raw_state_id", sa.Integer(), nullable=False),
        sa.Column("semantic_regime", sa.String(32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("blocked_flag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocking_reason", sa.Text(), nullable=True),
        sa.Column("model_family", sa.String(64), nullable=False),
        sa.Column("macro_context_state", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_condition_global_regime_snapshot_v1_condition_run_id",
        "condition_global_regime_snapshot_v1",
        ["condition_run_id"],
    )
    op.create_index(
        "ix_condition_global_regime_snapshot_v1_source_feature_run_id",
        "condition_global_regime_snapshot_v1",
        ["source_feature_run_id"],
    )
    op.create_index(
        "ix_condition_global_regime_snapshot_v1_bucket_start_utc",
        "condition_global_regime_snapshot_v1",
        ["bucket_start_utc"],
    )
    op.create_index(
        "ix_condition_global_regime_snapshot_v1_key",
        "condition_global_regime_snapshot_v1",
        ["bucket_start_utc", "semantic_regime"],
    )


def downgrade() -> None:
    op.drop_table("condition_global_regime_snapshot_v1")
    op.drop_table("condition_scoring_run")
    op.drop_table("feature_global_regime_input_15m_v1")
