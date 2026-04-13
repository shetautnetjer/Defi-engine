"""Initial schema — 20 tables for D5 Trading Engine

Revision ID: 001
Revises: None
Create Date: 2026-04-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === INFRASTRUCTURE ===

    op.create_table(
        "ingest_run",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("capture_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("records_captured", sa.Integer, nullable=True, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_ingest_run_run_id", "ingest_run", ["run_id"])
    op.create_index("ix_ingest_run_provider", "ingest_run", ["provider"])

    op.create_table(
        "capture_cursor",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("capture_type", sa.String(64), nullable=False),
        sa.Column("cursor_key", sa.String(128), nullable=False),
        sa.Column("cursor_value", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("provider", "capture_type", "cursor_key", name="uq_capture_cursor"),
    )

    op.create_table(
        "source_health_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("endpoint", sa.String(256), nullable=True),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("is_healthy", sa.Integer, nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("checked_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_source_health_provider", "source_health_event", ["provider"])

    # === RAW JUPITER ===

    op.create_table(
        "raw_jupiter_token_response",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("endpoint", sa.String(128), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_jup_tok_run", "raw_jupiter_token_response", ["ingest_run_id"])
    op.create_index("ix_raw_jup_tok_cap", "raw_jupiter_token_response", ["captured_at"])

    op.create_table(
        "raw_jupiter_price_response",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("mints_queried", sa.Text, nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_jup_price_run", "raw_jupiter_price_response", ["ingest_run_id"])
    op.create_index("ix_raw_jup_price_cap", "raw_jupiter_price_response", ["captured_at"])

    op.create_table(
        "raw_jupiter_quote_response",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("input_mint", sa.String(64), nullable=False),
        sa.Column("output_mint", sa.String(64), nullable=False),
        sa.Column("amount", sa.String(32), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_jup_quote_run", "raw_jupiter_quote_response", ["ingest_run_id"])
    op.create_index("ix_raw_jup_quote_in", "raw_jupiter_quote_response", ["input_mint"])
    op.create_index("ix_raw_jup_quote_out", "raw_jupiter_quote_response", ["output_mint"])
    op.create_index("ix_raw_jup_quote_cap", "raw_jupiter_quote_response", ["captured_at"])

    # === RAW HELIUS ===

    op.create_table(
        "raw_helius_enhanced_transaction",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="helius"),
        sa.Column("address", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=True),
        sa.Column("tx_type", sa.String(64), nullable=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_hel_tx_run", "raw_helius_enhanced_transaction", ["ingest_run_id"])
    op.create_index("ix_raw_hel_tx_addr", "raw_helius_enhanced_transaction", ["address"])
    op.create_index("ix_raw_hel_tx_sig", "raw_helius_enhanced_transaction", ["signature"])
    op.create_index("ix_raw_hel_tx_cap", "raw_helius_enhanced_transaction", ["captured_at"])

    op.create_table(
        "raw_helius_ws_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="helius"),
        sa.Column("subscription_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_hel_ws_run", "raw_helius_ws_event", ["ingest_run_id"])
    op.create_index("ix_raw_hel_ws_cap", "raw_helius_ws_event", ["captured_at"])

    # === RAW FRED ===

    op.create_table(
        "raw_fred_series_response",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="fred"),
        sa.Column("series_id", sa.String(32), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_fred_ser_run", "raw_fred_series_response", ["ingest_run_id"])
    op.create_index("ix_raw_fred_ser_id", "raw_fred_series_response", ["series_id"])
    op.create_index("ix_raw_fred_ser_cap", "raw_fred_series_response", ["captured_at"])

    op.create_table(
        "raw_fred_observation_response",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False, server_default="fred"),
        sa.Column("series_id", sa.String(32), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_fred_obs_run", "raw_fred_observation_response", ["ingest_run_id"])
    op.create_index("ix_raw_fred_obs_id", "raw_fred_observation_response", ["series_id"])
    op.create_index("ix_raw_fred_obs_cap", "raw_fred_observation_response", ["captured_at"])

    # === RAW MASSIVE ===

    op.create_table(
        "raw_massive_crypto_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="massive"),
        sa.Column("event_type", sa.String(64), nullable=True),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_raw_mass_run", "raw_massive_crypto_event", ["ingest_run_id"])
    op.create_index("ix_raw_mass_cap", "raw_massive_crypto_event", ["captured_at"])

    # === CANONICAL TRUTH ===

    op.create_table(
        "token_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("mint", sa.String(64), nullable=False, unique=True),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("decimals", sa.Integer, nullable=True),
        sa.Column("logo_uri", sa.Text, nullable=True),
        sa.Column("tags", sa.Text, nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("first_seen_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_token_reg_mint", "token_registry", ["mint"])
    op.create_index("ix_token_reg_symbol", "token_registry", ["symbol"])

    op.create_table(
        "token_metadata_snapshot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("mint", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("decimals", sa.Integer, nullable=True),
        sa.Column("daily_volume", sa.Float, nullable=True),
        sa.Column("freeze_authority", sa.String(64), nullable=True),
        sa.Column("mint_authority", sa.String(64), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_token_meta_run", "token_metadata_snapshot", ["ingest_run_id"])
    op.create_index("ix_token_meta_mint", "token_metadata_snapshot", ["mint"])
    op.create_index("ix_token_meta_mint_cap", "token_metadata_snapshot", ["mint", "captured_at"])

    op.create_table(
        "token_price_snapshot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("mint", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("price_usd", sa.Float, nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_price_run", "token_price_snapshot", ["ingest_run_id"])
    op.create_index("ix_price_mint", "token_price_snapshot", ["mint"])
    op.create_index("ix_price_mint_cap", "token_price_snapshot", ["mint", "captured_at"])

    op.create_table(
        "quote_snapshot",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("input_mint", sa.String(64), nullable=False),
        sa.Column("output_mint", sa.String(64), nullable=False),
        sa.Column("input_amount", sa.String(32), nullable=False),
        sa.Column("output_amount", sa.String(32), nullable=True),
        sa.Column("price_impact_pct", sa.Float, nullable=True),
        sa.Column("slippage_bps", sa.Integer, nullable=True),
        sa.Column("route_plan_json", sa.Text, nullable=True),
        sa.Column("other_amount_threshold", sa.String(32), nullable=True),
        sa.Column("swap_mode", sa.String(16), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="jupiter"),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_quote_run", "quote_snapshot", ["ingest_run_id"])
    op.create_index("ix_quote_in", "quote_snapshot", ["input_mint"])
    op.create_index("ix_quote_out", "quote_snapshot", ["output_mint"])
    op.create_index("ix_quote_pair_cap", "quote_snapshot", ["input_mint", "output_mint", "captured_at"])

    op.create_table(
        "fred_series_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("series_id", sa.String(32), nullable=False, unique=True),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("frequency", sa.String(16), nullable=True),
        sa.Column("units", sa.String(64), nullable=True),
        sa.Column("seasonal_adjustment", sa.String(32), nullable=True),
        sa.Column("last_updated", sa.DateTime, nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="fred"),
        sa.Column("first_seen_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_fred_reg_id", "fred_series_registry", ["series_id"])

    op.create_table(
        "fred_observation",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ingest_run_id", sa.String(64), sa.ForeignKey("ingest_run.run_id"), nullable=False),
        sa.Column("series_id", sa.String(32), nullable=False),
        sa.Column("observation_date", sa.String(10), nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("realtime_start", sa.String(10), nullable=True),
        sa.Column("realtime_end", sa.String(10), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="fred"),
        sa.Column("captured_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_fred_obs_run", "fred_observation", ["ingest_run_id"])
    op.create_index("ix_fred_obs_series", "fred_observation", ["series_id"])
    op.create_index("ix_fred_obs_series_date", "fred_observation", ["series_id", "observation_date"])

    # === REGISTRIES ===

    op.create_table(
        "program_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("program_id", sa.String(64), nullable=False, unique=True),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_prog_reg_id", "program_registry", ["program_id"])

    op.create_table(
        "solana_address_registry",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("address", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(128), nullable=True),
        sa.Column("address_type", sa.String(32), nullable=True),
        sa.Column("is_tracked", sa.Integer, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_sol_addr_reg", "solana_address_registry", ["address"])

    # === RESEARCH SCAFFOLDING ===

    op.create_table(
        "feature_materialization_run",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("feature_set", sa.String(128), nullable=False),
        sa.Column("source_tables", sa.Text, nullable=True),
        sa.Column("row_count", sa.Integer, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_feat_run_id", "feature_materialization_run", ["run_id"])

    op.create_table(
        "experiment_run",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.String(64), nullable=False, unique=True),
        sa.Column("experiment_name", sa.String(128), nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=True),
        sa.Column("config_json", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("conclusion", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_exp_run_id", "experiment_run", ["run_id"])

    op.create_table(
        "experiment_metric",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("experiment_run_id", sa.String(64), sa.ForeignKey("experiment_run.run_id"), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Float, nullable=True),
        sa.Column("metric_metadata", sa.Text, nullable=True),
        sa.Column("recorded_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_exp_metric_run", "experiment_metric", ["experiment_run_id"])
    op.create_index("ix_exp_metric_run_name", "experiment_metric", ["experiment_run_id", "metric_name"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("experiment_metric")
    op.drop_table("experiment_run")
    op.drop_table("feature_materialization_run")
    op.drop_table("solana_address_registry")
    op.drop_table("program_registry")
    op.drop_table("fred_observation")
    op.drop_table("fred_series_registry")
    op.drop_table("quote_snapshot")
    op.drop_table("token_price_snapshot")
    op.drop_table("token_metadata_snapshot")
    op.drop_table("token_registry")
    op.drop_table("raw_massive_crypto_event")
    op.drop_table("raw_fred_observation_response")
    op.drop_table("raw_fred_series_response")
    op.drop_table("raw_helius_ws_event")
    op.drop_table("raw_helius_enhanced_transaction")
    op.drop_table("raw_jupiter_quote_response")
    op.drop_table("raw_jupiter_price_response")
    op.drop_table("raw_jupiter_token_response")
    op.drop_table("source_health_event")
    op.drop_table("capture_cursor")
    op.drop_table("ingest_run")
