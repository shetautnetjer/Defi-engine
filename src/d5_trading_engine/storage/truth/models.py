"""
D5 Trading Engine — ORM Models (Canonical Truth Schema)

The canonical truth surface lives in SQLite and holds:
- infrastructure receipts
- raw per-source payload receipts
- normalized spot / macro / chain event tables
- lightweight research scaffolding
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models."""


class IngestRun(Base):
    """Track each capture invocation."""

    __tablename__ = "ingest_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    provider = Column(String(32), nullable=False, index=True)
    capture_type = Column(String(64), nullable=False)
    status = Column(String(16), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    records_captured = Column(Integer, nullable=True, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class CaptureCursor(Base):
    """Bookmarks for resumable fetching."""

    __tablename__ = "capture_cursor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False)
    capture_type = Column(String(64), nullable=False)
    cursor_key = Column(String(128), nullable=False)
    cursor_value = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "capture_type", "cursor_key", name="uq_capture_cursor"),
    )


class SourceHealthEvent(Base):
    """Provider liveness tracking."""

    __tablename__ = "source_health_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    provider = Column(String(32), nullable=False, index=True)
    endpoint = Column(String(256), nullable=True)
    status_code = Column(Integer, nullable=True)
    latency_ms = Column(Float, nullable=True)
    is_healthy = Column(Integer, nullable=False, default=1)
    error_message = Column(Text, nullable=True)
    checked_at = Column(DateTime, nullable=False)


class RawJupiterTokenResponse(Base):
    """Raw Jupiter token API responses."""

    __tablename__ = "raw_jupiter_token_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    endpoint = Column(String(128), nullable=False)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawJupiterPriceResponse(Base):
    """Raw Jupiter price API responses."""

    __tablename__ = "raw_jupiter_price_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    mints_queried = Column(Text, nullable=False)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawJupiterQuoteResponse(Base):
    """Raw Jupiter quote API responses."""

    __tablename__ = "raw_jupiter_quote_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    input_mint = Column(String(64), nullable=False, index=True)
    output_mint = Column(String(64), nullable=False, index=True)
    amount = Column(String(32), nullable=False)
    request_direction = Column(String(16), nullable=True)
    requested_at = Column(DateTime, nullable=True)
    response_latency_ms = Column(Float, nullable=True)
    source_event_time_utc = Column(DateTime, nullable=True)
    source_time_raw = Column(Text, nullable=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawHeliusEnhancedTransaction(Base):
    """Raw Helius enhanced transaction payloads."""

    __tablename__ = "raw_helius_enhanced_transaction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="helius")
    address = Column(String(64), nullable=False, index=True)
    signature = Column(String(128), nullable=True, index=True)
    tx_type = Column(String(64), nullable=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawHeliusAccountDiscovery(Base):
    """Raw Helius account-discovery payloads."""

    __tablename__ = "raw_helius_account_discovery"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="helius")
    address = Column(String(64), nullable=False, index=True)
    owner_program_id = Column(String(64), nullable=True, index=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawHeliusWsEvent(Base):
    """Raw Helius websocket event payloads."""

    __tablename__ = "raw_helius_ws_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), nullable=True, index=True)
    provider = Column(String(32), nullable=False, default="helius")
    subscription_id = Column(String(64), nullable=True)
    event_type = Column(String(64), nullable=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawFredSeriesResponse(Base):
    """Raw FRED series metadata responses."""

    __tablename__ = "raw_fred_series_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="fred")
    series_id = Column(String(32), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawFredObservationResponse(Base):
    """Raw FRED observation payloads."""

    __tablename__ = "raw_fred_observation_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="fred")
    series_id = Column(String(32), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawMassiveCryptoEvent(Base):
    """Raw Massive crypto event payloads."""

    __tablename__ = "raw_massive_crypto_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), nullable=True, index=True)
    provider = Column(String(32), nullable=False, default="massive")
    event_type = Column(String(64), nullable=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class TokenRegistry(Base):
    """Canonical token identity — one row per unique token."""

    __tablename__ = "token_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    mint = Column(String(64), nullable=False, unique=True, index=True)
    symbol = Column(String(32), nullable=True, index=True)
    name = Column(String(128), nullable=True)
    decimals = Column(Integer, nullable=True)
    logo_uri = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    first_seen_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class TokenMetadataSnapshot(Base):
    """Point-in-time token metadata snapshot."""

    __tablename__ = "token_metadata_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    mint = Column(String(64), nullable=False, index=True)
    symbol = Column(String(32), nullable=True)
    name = Column(String(128), nullable=True)
    decimals = Column(Integer, nullable=True)
    daily_volume = Column(Float, nullable=True)
    freeze_authority = Column(String(64), nullable=True)
    mint_authority = Column(String(64), nullable=True)
    metadata_json = Column(Text, nullable=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    captured_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("ix_token_meta_mint_captured", "mint", "captured_at"),
    )


class TokenPriceSnapshot(Base):
    """Normalized price captures from Jupiter Price API."""

    __tablename__ = "token_price_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    mint = Column(String(64), nullable=False, index=True)
    symbol = Column(String(32), nullable=True)
    price_usd = Column(Float, nullable=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    captured_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("ix_price_mint_captured", "mint", "captured_at"),
    )


class QuoteSnapshot(Base):
    """Normalized route-aware quote captures from Jupiter Swap API."""

    __tablename__ = "quote_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    input_mint = Column(String(64), nullable=False, index=True)
    output_mint = Column(String(64), nullable=False, index=True)
    input_amount = Column(String(32), nullable=False)
    output_amount = Column(String(32), nullable=True)
    price_impact_pct = Column(Float, nullable=True)
    slippage_bps = Column(Integer, nullable=True)
    route_plan_json = Column(Text, nullable=True)
    other_amount_threshold = Column(String(32), nullable=True)
    swap_mode = Column(String(16), nullable=True)
    request_direction = Column(String(16), nullable=True)
    requested_at = Column(DateTime, nullable=True)
    response_latency_ms = Column(Float, nullable=True)
    source_event_time_utc = Column(DateTime, nullable=True, index=True)
    source_time_raw = Column(Text, nullable=True)
    event_date_utc = Column(String(10), nullable=True)
    hour_utc = Column(Integer, nullable=True)
    minute_of_day_utc = Column(Integer, nullable=True)
    weekday_utc = Column(Integer, nullable=True)
    time_quality = Column(String(16), nullable=True)
    provider = Column(String(32), nullable=False, default="jupiter")
    captured_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("ix_quote_pair_captured", "input_mint", "output_mint", "captured_at"),
    )


class FredSeriesRegistry(Base):
    """FRED series identity and metadata."""

    __tablename__ = "fred_series_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(String(32), nullable=False, unique=True, index=True)
    title = Column(String(256), nullable=True)
    frequency = Column(String(16), nullable=True)
    units = Column(String(64), nullable=True)
    seasonal_adjustment = Column(String(32), nullable=True)
    last_updated = Column(DateTime, nullable=True)
    provider = Column(String(32), nullable=False, default="fred")
    first_seen_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class FredObservation(Base):
    """FRED observation values with realtime/vintage fields."""

    __tablename__ = "fred_observation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    series_id = Column(String(32), nullable=False, index=True)
    observation_date = Column(String(10), nullable=False)
    value = Column(Float, nullable=True)
    realtime_start = Column(String(10), nullable=True)
    realtime_end = Column(String(10), nullable=True)
    provider = Column(String(32), nullable=False, default="fred")
    captured_at = Column(DateTime, nullable=False, index=True)

    __table_args__ = (
        Index("ix_fred_obs_series_date", "series_id", "observation_date"),
    )


class ProgramRegistry(Base):
    """Known Solana program IDs."""

    __tablename__ = "program_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    program_id = Column(String(64), nullable=False, unique=True, index=True)
    name = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class SolanaAddressRegistry(Base):
    """Tracked Solana addresses."""

    __tablename__ = "solana_address_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    address = Column(String(64), nullable=False, unique=True, index=True)
    label = Column(String(128), nullable=True)
    address_type = Column(String(32), nullable=True)
    is_tracked = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class SolanaTransferEvent(Base):
    """First bounded chain-event projection from Helius transaction capture."""

    __tablename__ = "solana_transfer_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    signature = Column(String(128), nullable=True, index=True)
    slot = Column(Integer, nullable=True, index=True)
    mint = Column(String(64), nullable=True, index=True)
    source_address = Column(String(64), nullable=True, index=True)
    destination_address = Column(String(64), nullable=True, index=True)
    amount_raw = Column(String(64), nullable=True)
    amount_float = Column(Float, nullable=True)
    decimals = Column(Integer, nullable=True)
    program_id = Column(String(64), nullable=True, index=True)
    fee_lamports = Column(Integer, nullable=True)
    transfer_type = Column(String(16), nullable=False, default="token")
    source_event_time_utc = Column(DateTime, nullable=True, index=True)
    captured_at_utc = Column(DateTime, nullable=False, index=True)
    source_time_raw = Column(Text, nullable=True)
    event_date_utc = Column(String(10), nullable=True)
    hour_utc = Column(Integer, nullable=True)
    minute_of_day_utc = Column(Integer, nullable=True)
    weekday_utc = Column(Integer, nullable=True)
    time_quality = Column(String(16), nullable=True)

    __table_args__ = (
        Index("ix_sol_transfer_signature_time", "signature", "source_event_time_utc"),
    )


class MarketInstrumentRegistry(Base):
    """Venue product metadata for exchange-style market data sources."""

    __tablename__ = "market_instrument_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    venue = Column(String(32), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    base_symbol = Column(String(32), nullable=True, index=True)
    quote_symbol = Column(String(32), nullable=True, index=True)
    product_type = Column(String(32), nullable=True)
    status = Column(String(32), nullable=True)
    price_increment = Column(String(32), nullable=True)
    base_increment = Column(String(32), nullable=True)
    quote_increment = Column(String(32), nullable=True)
    first_seen_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("venue", "product_id", name="uq_market_instrument"),
    )


class MarketCandle(Base):
    """Normalized OHLCV bars from exchange-style providers."""

    __tablename__ = "market_candle"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    venue = Column(String(32), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    granularity = Column(String(32), nullable=False)
    start_time_utc = Column(DateTime, nullable=False, index=True)
    end_time_utc = Column(DateTime, nullable=True)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)
    source_event_time_utc = Column(DateTime, nullable=True, index=True)
    captured_at_utc = Column(DateTime, nullable=False)
    source_time_raw = Column(Text, nullable=True)
    event_date_utc = Column(String(10), nullable=True)
    hour_utc = Column(Integer, nullable=True)
    minute_of_day_utc = Column(Integer, nullable=True)
    weekday_utc = Column(Integer, nullable=True)
    time_quality = Column(String(16), nullable=True)

    __table_args__ = (
        Index("ix_market_candle_key", "venue", "product_id", "granularity", "start_time_utc"),
    )


class MarketTradeEvent(Base):
    """Normalized trade prints from exchange-style providers."""

    __tablename__ = "market_trade_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    venue = Column(String(32), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    trade_id = Column(String(128), nullable=True, index=True)
    side = Column(String(16), nullable=True)
    price = Column(Float, nullable=True)
    size = Column(Float, nullable=True)
    source_event_time_utc = Column(DateTime, nullable=True, index=True)
    captured_at_utc = Column(DateTime, nullable=False)
    source_time_raw = Column(Text, nullable=True)
    event_date_utc = Column(String(10), nullable=True)
    hour_utc = Column(Integer, nullable=True)
    minute_of_day_utc = Column(Integer, nullable=True)
    weekday_utc = Column(Integer, nullable=True)
    time_quality = Column(String(16), nullable=True)

    __table_args__ = (
        Index("ix_market_trade_key", "venue", "product_id", "source_event_time_utc"),
    )


class OrderBookL2Event(Base):
    """Normalized L2 book snapshots or updates from exchange-style providers."""

    __tablename__ = "order_book_l2_event"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), ForeignKey("ingest_run.run_id"), nullable=False, index=True)
    venue = Column(String(32), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    event_kind = Column(String(16), nullable=False, default="snapshot")
    best_bid = Column(Float, nullable=True)
    best_ask = Column(Float, nullable=True)
    spread_absolute = Column(Float, nullable=True)
    spread_bps = Column(Float, nullable=True)
    bids_json = Column(Text, nullable=True)
    asks_json = Column(Text, nullable=True)
    source_event_time_utc = Column(DateTime, nullable=True, index=True)
    captured_at_utc = Column(DateTime, nullable=False)
    source_time_raw = Column(Text, nullable=True)
    event_date_utc = Column(String(10), nullable=True)
    hour_utc = Column(Integer, nullable=True)
    minute_of_day_utc = Column(Integer, nullable=True)
    weekday_utc = Column(Integer, nullable=True)
    time_quality = Column(String(16), nullable=True)

    __table_args__ = (
        Index("ix_order_book_key", "venue", "product_id", "source_event_time_utc"),
    )


class FeatureMaterializationRun(Base):
    """Feature pipeline tracking."""

    __tablename__ = "feature_materialization_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    feature_set = Column(String(128), nullable=False)
    source_tables = Column(Text, nullable=True)
    freshness_snapshot_json = Column(Text, nullable=True)
    input_window_start_utc = Column(DateTime, nullable=True)
    input_window_end_utc = Column(DateTime, nullable=True)
    row_count = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class FeatureSpotChainMacroMinuteV1(Base):
    """First bounded feature table for spot, chain, and macro minute context."""

    __tablename__ = "feature_spot_chain_macro_minute_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    feature_minute_utc = Column(DateTime, nullable=False, index=True)
    mint = Column(String(64), nullable=False, index=True)
    symbol = Column(String(32), nullable=True, index=True)
    coinbase_product_id = Column(String(64), nullable=True, index=True)
    jupiter_price_usd = Column(Float, nullable=True)
    quote_count = Column(Integer, nullable=False, default=0)
    mean_quote_price_impact_pct = Column(Float, nullable=True)
    mean_quote_response_latency_ms = Column(Float, nullable=True)
    coinbase_close = Column(Float, nullable=True)
    coinbase_trade_count = Column(Integer, nullable=False, default=0)
    coinbase_trade_size_sum = Column(Float, nullable=True)
    coinbase_book_spread_bps = Column(Float, nullable=True)
    chain_transfer_count = Column(Integer, nullable=False, default=0)
    chain_amount_in = Column(Float, nullable=True)
    chain_amount_out = Column(Float, nullable=True)
    fred_dff = Column(Float, nullable=True)
    fred_t10y2y = Column(Float, nullable=True)
    fred_vixcls = Column(Float, nullable=True)
    fred_dgs10 = Column(Float, nullable=True)
    fred_dtwexbgs = Column(Float, nullable=True)
    event_date_utc = Column(String(10), nullable=True)
    hour_utc = Column(Integer, nullable=True)
    minute_of_day_utc = Column(Integer, nullable=True)
    weekday_utc = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_feature_spot_chain_macro_minute_key", "mint", "feature_minute_utc"),
    )


class ExperimentRun(Base):
    """Research experiment tracking."""

    __tablename__ = "experiment_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    experiment_name = Column(String(128), nullable=False)
    hypothesis = Column(Text, nullable=True)
    config_json = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="running")
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    conclusion = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False)


class ExperimentMetric(Base):
    """Experiment metric values."""

    __tablename__ = "experiment_metric"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_run_id = Column(
        String(64),
        ForeignKey("experiment_run.run_id"),
        nullable=False,
        index=True,
    )
    metric_name = Column(String(64), nullable=False)
    metric_value = Column(Float, nullable=True)
    metric_metadata = Column(Text, nullable=True)
    recorded_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_exp_metric_run_name", "experiment_run_id", "metric_name"),
    )
