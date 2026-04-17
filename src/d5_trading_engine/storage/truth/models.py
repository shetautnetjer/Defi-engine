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


class FeatureGlobalRegimeInput15mV1(Base):
    """Market-wide 15-minute regime inputs derived from canonical truth."""

    __tablename__ = "feature_global_regime_input_15m_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    bucket_start_utc = Column(DateTime, nullable=False, index=True)
    regime_key = Column(String(32), nullable=False, default="global")
    proxy_products_json = Column(Text, nullable=True)
    proxy_count = Column(Integer, nullable=False, default=0)
    market_return_mean_15m = Column(Float, nullable=True)
    market_return_std_15m = Column(Float, nullable=True)
    market_realized_vol_15m = Column(Float, nullable=True)
    market_volume_sum_15m = Column(Float, nullable=True)
    market_trade_count_15m = Column(Integer, nullable=False, default=0)
    market_trade_size_sum_15m = Column(Float, nullable=True)
    market_book_spread_bps_mean_15m = Column(Float, nullable=True)
    market_return_mean_4h = Column(Float, nullable=True)
    market_realized_vol_4h = Column(Float, nullable=True)
    macro_context_available = Column(Integer, nullable=False, default=0)
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
        Index("ix_feature_global_regime_input_15m_key", "regime_key", "bucket_start_utc"),
    )


class ConditionScoringRun(Base):
    """Track condition scoring runs and the model semantics they produced."""

    __tablename__ = "condition_scoring_run"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), nullable=False, unique=True, index=True)
    condition_set = Column(String(128), nullable=False)
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    model_family = Column(String(64), nullable=False)
    training_window_start_utc = Column(DateTime, nullable=True)
    training_window_end_utc = Column(DateTime, nullable=True)
    scored_bucket_start_utc = Column(DateTime, nullable=True)
    state_semantics_json = Column(Text, nullable=True)
    model_params_json = Column(Text, nullable=True)
    status = Column(String(16), nullable=False, default="running")
    confidence = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False)


class ConditionGlobalRegimeSnapshotV1(Base):
    """Latest scored regime snapshot for a closed 15-minute bucket."""

    __tablename__ = "condition_global_regime_snapshot_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    condition_run_id = Column(
        String(64),
        ForeignKey("condition_scoring_run.run_id"),
        nullable=False,
        index=True,
    )
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    bucket_start_utc = Column(DateTime, nullable=False, index=True)
    raw_state_id = Column(Integer, nullable=False)
    semantic_regime = Column(String(32), nullable=False)
    confidence = Column(Float, nullable=False)
    blocked_flag = Column(Integer, nullable=False, default=0)
    blocking_reason = Column(Text, nullable=True)
    model_family = Column(String(64), nullable=False)
    macro_context_state = Column(String(32), nullable=True)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index(
            "ix_condition_global_regime_snapshot_v1_key",
            "bucket_start_utc",
            "semantic_regime",
        ),
    )


class PolicyGlobalRegimeTraceV1(Base):
    """Policy-owned trace for bounded global regime eligibility decisions."""

    __tablename__ = "policy_global_regime_trace_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    condition_run_id = Column(
        String(64),
        ForeignKey("condition_scoring_run.run_id"),
        nullable=False,
        index=True,
    )
    condition_snapshot_id = Column(
        Integer,
        ForeignKey("condition_global_regime_snapshot_v1.id"),
        nullable=False,
        index=True,
    )
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    bucket_start_utc = Column(DateTime, nullable=False, index=True)
    semantic_regime = Column(String(32), nullable=False)
    condition_confidence = Column(Float, nullable=False)
    macro_context_state = Column(String(32), nullable=True)
    condition_blocked_flag = Column(Integer, nullable=False, default=0)
    condition_blocking_reason = Column(Text, nullable=True)
    policy_state = Column(String(32), nullable=False)
    advisory_bias = Column(String(32), nullable=False)
    allow_new_long_hypotheses = Column(Integer, nullable=False, default=0)
    allow_new_short_hypotheses = Column(Integer, nullable=False, default=0)
    config_hash = Column(String(64), nullable=False)
    config_version = Column(Integer, nullable=False)
    config_status = Column(String(32), nullable=False)
    reason_codes_json = Column(Text, nullable=False)
    trace_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index(
            "ix_policy_global_regime_trace_v1_key",
            "bucket_start_utc",
            "policy_state",
        ),
    )


class RiskGlobalRegimeGateV1(Base):
    """Risk-owned veto receipt over persisted global regime policy truth."""

    __tablename__ = "risk_global_regime_gate_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_trace_id = Column(
        Integer,
        ForeignKey("policy_global_regime_trace_v1.id"),
        nullable=False,
        index=True,
    )
    condition_run_id = Column(
        String(64),
        ForeignKey("condition_scoring_run.run_id"),
        nullable=False,
        index=True,
    )
    condition_snapshot_id = Column(
        Integer,
        ForeignKey("condition_global_regime_snapshot_v1.id"),
        nullable=False,
        index=True,
    )
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    bucket_start_utc = Column(DateTime, nullable=False, index=True)
    policy_state = Column(String(32), nullable=False)
    risk_state = Column(String(32), nullable=False)
    macro_context_state = Column(String(32), nullable=True)
    condition_blocked_flag = Column(Integer, nullable=False, default=0)
    stale_data_authorized_flag = Column(Integer, nullable=False, default=0)
    unresolved_input_flag = Column(Integer, nullable=False, default=0)
    anomaly_signal_state = Column(String(32), nullable=False, default="not_owned")
    reason_codes_json = Column(Text, nullable=False)
    trace_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index(
            "ix_risk_global_regime_gate_v1_key",
            "bucket_start_utc",
            "risk_state",
        ),
    )


class ExecutionIntentV1(Base):
    """Runtime-owned execution intent between risk and settlement."""

    __tablename__ = "execution_intent_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intent_key = Column(String(128), nullable=False, unique=True, index=True)
    risk_verdict_id = Column(
        Integer,
        ForeignKey("risk_global_regime_gate_v1.id"),
        nullable=True,
        index=True,
    )
    policy_trace_id = Column(
        Integer,
        ForeignKey("policy_global_regime_trace_v1.id"),
        nullable=True,
        index=True,
    )
    condition_snapshot_id = Column(
        Integer,
        ForeignKey("condition_global_regime_snapshot_v1.id"),
        nullable=True,
        index=True,
    )
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=True,
        index=True,
    )
    quote_snapshot_id = Column(
        Integer,
        ForeignKey("quote_snapshot.id"),
        nullable=True,
        index=True,
    )
    bucket_start_utc = Column(DateTime, nullable=True, index=True)
    intent_state = Column(String(16), nullable=False, index=True)
    venue = Column(String(32), nullable=False)
    settlement_model = Column(String(32), nullable=False)
    strategy_family = Column(String(64), nullable=False)
    policy_state = Column(String(32), nullable=True)
    risk_state = Column(String(32), nullable=True)
    request_direction = Column(String(16), nullable=True)
    intent_side = Column(String(16), nullable=True)
    intent_role = Column(String(16), nullable=False, default="entry")
    entry_intent = Column(String(32), nullable=False)
    exit_intent = Column(String(32), nullable=False)
    stop_intent = Column(String(32), nullable=False)
    input_mint = Column(String(64), nullable=True)
    output_mint = Column(String(64), nullable=True)
    quote_size_lamports = Column(Integer, nullable=True)
    quoted_output_amount = Column(String(32), nullable=True)
    reason_codes_json = Column(Text, nullable=False)
    trace_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        Index("ix_execution_intent_v1_risk_state", "intent_state", "risk_state"),
    )


class PaperSession(Base):
    """Settlement-owned paper session lifecycle receipt."""

    __tablename__ = "paper_session"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_key = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, index=True)
    base_currency = Column(String(16), nullable=False, default="USDC")
    quote_size_lamports = Column(Integer, nullable=False, default=0)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    starting_cash_usdc = Column(Float, nullable=False, default=0.0)
    ending_cash_usdc = Column(Float, nullable=True)
    reason_codes_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class PaperFill(Base):
    """Append-only paper fill receipt tied to explicit upstream provenance."""

    __tablename__ = "paper_fill"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("paper_session.id"), nullable=False, index=True)
    execution_intent_id = Column(
        Integer,
        ForeignKey("execution_intent_v1.id"),
        nullable=True,
        index=True,
    )
    risk_verdict_id = Column(
        Integer,
        ForeignKey("risk_global_regime_gate_v1.id"),
        nullable=False,
        index=True,
    )
    policy_trace_id = Column(
        Integer,
        ForeignKey("policy_global_regime_trace_v1.id"),
        nullable=False,
        index=True,
    )
    condition_snapshot_id = Column(
        Integer,
        ForeignKey("condition_global_regime_snapshot_v1.id"),
        nullable=False,
        index=True,
    )
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    quote_snapshot_id = Column(
        Integer,
        ForeignKey("quote_snapshot.id"),
        nullable=False,
        index=True,
    )
    policy_state = Column(String(32), nullable=False)
    risk_state = Column(String(32), nullable=False)
    request_direction = Column(String(16), nullable=False)
    input_mint = Column(String(64), nullable=False)
    output_mint = Column(String(64), nullable=False)
    input_amount = Column(String(32), nullable=False)
    output_amount = Column(String(32), nullable=False)
    fill_price_usdc = Column(Float, nullable=False)
    price_impact_pct = Column(Float, nullable=True)
    slippage_bps = Column(Integer, nullable=True)
    fill_side = Column(String(16), nullable=False)
    fill_role = Column(String(16), nullable=False)
    created_at = Column(DateTime, nullable=False)


class PaperPosition(Base):
    """Current paper position state for one mint inside one paper session."""

    __tablename__ = "paper_position"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("paper_session.id"), nullable=False, index=True)
    mint = Column(String(64), nullable=False, index=True)
    net_quantity = Column(Float, nullable=False)
    cost_basis_usdc = Column(Float, nullable=False)
    last_fill_id = Column(Integer, ForeignKey("paper_fill.id"), nullable=False, index=True)
    last_mark_source = Column(String(32), nullable=True)
    last_mark_quote_snapshot_id = Column(
        Integer,
        ForeignKey("quote_snapshot.id"),
        nullable=True,
        index=True,
    )
    last_mark_price_usdc = Column(Float, nullable=True)
    last_marked_at = Column(DateTime, nullable=True)
    realized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "mint", name="uq_paper_position_session_mint"),
    )


class PaperSessionReport(Base):
    """Settlement-owned report derived from paper sessions, fills, and positions."""

    __tablename__ = "paper_session_report"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("paper_session.id"), nullable=False, index=True)
    report_type = Column(String(32), nullable=False)
    cash_usdc = Column(Float, nullable=False)
    position_value_usdc = Column(Float, nullable=False)
    equity_usdc = Column(Float, nullable=False)
    realized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    mark_method = Column(String(32), nullable=False)
    mark_inputs_json = Column(Text, nullable=False)
    reason_codes_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class BacktestSessionV1(Base):
    """Settlement-owned backtest replay session with explicit assumptions."""

    __tablename__ = "backtest_session_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_key = Column(String(128), nullable=False, unique=True, index=True)
    status = Column(String(16), nullable=False, index=True)
    instrument_family = Column(String(16), nullable=False, default="spot")
    venue = Column(String(32), nullable=False)
    base_currency = Column(String(16), nullable=False, default="USDC")
    bucket_granularity = Column(String(16), nullable=False)
    fee_bps = Column(Integer, nullable=False)
    slippage_bps = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    mark_method = Column(String(32), nullable=False)
    metadata_json = Column(Text, nullable=False)
    starting_cash_usdc = Column(Float, nullable=False, default=0.0)
    ending_cash_usdc = Column(Float, nullable=True)
    opened_at = Column(DateTime, nullable=False)
    closed_at = Column(DateTime, nullable=True)
    reason_codes_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class BacktestFillV1(Base):
    """Append-only backtest fill receipt with explicit replay assumptions."""

    __tablename__ = "backtest_fill_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("backtest_session_v1.id"),
        nullable=False,
        index=True,
    )
    event_time = Column(DateTime, nullable=False, index=True)
    replay_reference = Column(String(128), nullable=False)
    mint = Column(String(64), nullable=False, index=True)
    side = Column(String(16), nullable=False)
    input_amount = Column(String(32), nullable=False)
    output_amount = Column(String(32), nullable=False)
    fill_price_usdc = Column(Float, nullable=False)
    fee_bps = Column(Integer, nullable=False)
    fee_usdc = Column(Float, nullable=False)
    slippage_bps = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    reason_codes_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


class BacktestPositionV1(Base):
    """Current backtest position state for one mint inside one replay session."""

    __tablename__ = "backtest_position_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("backtest_session_v1.id"),
        nullable=False,
        index=True,
    )
    mint = Column(String(64), nullable=False, index=True)
    net_quantity = Column(Float, nullable=False)
    cost_basis_usdc = Column(Float, nullable=False)
    last_fill_id = Column(
        Integer,
        ForeignKey("backtest_fill_v1.id"),
        nullable=False,
        index=True,
    )
    last_mark_source = Column(String(32), nullable=True)
    last_mark_reference = Column(String(128), nullable=True)
    last_mark_price_usdc = Column(Float, nullable=True)
    last_marked_at = Column(DateTime, nullable=True)
    realized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "mint", name="uq_backtest_position_session_mint"),
    )


class BacktestSessionReportV1(Base):
    """Settlement-owned report derived from backtest sessions and replay fills."""

    __tablename__ = "backtest_session_report_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        Integer,
        ForeignKey("backtest_session_v1.id"),
        nullable=False,
        index=True,
    )
    report_type = Column(String(32), nullable=False)
    cash_usdc = Column(Float, nullable=False)
    position_value_usdc = Column(Float, nullable=False)
    equity_usdc = Column(Float, nullable=False)
    realized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    unrealized_pnl_usdc = Column(Float, nullable=False, default=0.0)
    mark_method = Column(String(32), nullable=False)
    mark_inputs_json = Column(Text, nullable=False)
    reason_codes_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)


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


class ExperimentRealizedFeedbackV1(Base):
    """Research-owned advisory comparison between shadow context and paper outcomes."""

    __tablename__ = "experiment_realized_feedback_v1"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment_run_id = Column(
        String(64),
        ForeignKey("experiment_run.run_id"),
        nullable=False,
        index=True,
    )
    paper_fill_id = Column(Integer, ForeignKey("paper_fill.id"), nullable=False, index=True)
    paper_session_id = Column(Integer, ForeignKey("paper_session.id"), nullable=False, index=True)
    paper_position_id = Column(Integer, ForeignKey("paper_position.id"), nullable=True, index=True)
    paper_session_report_id = Column(
        Integer,
        ForeignKey("paper_session_report.id"),
        nullable=True,
        index=True,
    )
    source_feature_run_id = Column(
        String(64),
        ForeignKey("feature_materialization_run.run_id"),
        nullable=False,
        index=True,
    )
    matched_mint = Column(String(64), nullable=False, index=True)
    matched_bucket_15m_utc = Column(DateTime, nullable=True, index=True)
    matched_bucket_5m_utc = Column(DateTime, nullable=True, index=True)
    comparison_state = Column(String(16), nullable=False, index=True)
    match_method = Column(String(128), nullable=False)
    match_tolerance_seconds = Column(Integer, nullable=False)
    shadow_context_json = Column(Text, nullable=False)
    realized_outcome_json = Column(Text, nullable=False)
    reason_codes_json = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "experiment_run_id",
            "paper_fill_id",
            name="uq_experiment_realized_feedback_run_fill",
        ),
        Index(
            "ix_experiment_realized_feedback_run_state",
            "experiment_run_id",
            "comparison_state",
        ),
    )
