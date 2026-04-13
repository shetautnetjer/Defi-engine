"""Raw Coinbase market-data storage models."""

from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for Coinbase raw-storage models."""


class RawCoinbaseProduct(Base):
    """Raw Coinbase product listing payloads."""

    __tablename__ = "raw_coinbase_product"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=True, index=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawCoinbaseCandleResponse(Base):
    """Raw Coinbase candle responses."""

    __tablename__ = "raw_coinbase_candle_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    granularity = Column(String(32), nullable=False)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawCoinbaseTradeResponse(Base):
    """Raw Coinbase market-trade responses."""

    __tablename__ = "raw_coinbase_trade_response"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)


class RawCoinbaseBookSnapshot(Base):
    """Raw Coinbase product-book snapshots."""

    __tablename__ = "raw_coinbase_book_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ingest_run_id = Column(String(64), nullable=False, index=True)
    product_id = Column(String(64), nullable=False, index=True)
    payload = Column(Text, nullable=False)
    captured_at = Column(DateTime, nullable=False, index=True)
