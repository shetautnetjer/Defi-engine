"""Normalize Massive crypto reference, snapshot, and minute-aggregate payloads."""

from __future__ import annotations

from datetime import UTC, datetime

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import derive_event_time_fields, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import MarketCandle, MarketInstrumentRegistry

log = get_logger(__name__, normalizer="massive")


def _as_float(value) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _parse_epoch_any(value) -> datetime | None:
    if value in (None, ""):
        return None
    raw = float(value)
    if raw > 1e18:
        raw = raw / 1_000_000_000
    elif raw > 1e15:
        raw = raw / 1_000_000
    elif raw > 1e12:
        raw = raw / 1000
    return datetime.fromtimestamp(raw, tz=UTC)


def _infer_symbols(product_id: str) -> tuple[str | None, str | None]:
    ticker = product_id.replace("X:", "")
    for quote_symbol in ("USDC", "USD", "BTC", "ETH"):
        if ticker.endswith(quote_symbol) and len(ticker) > len(quote_symbol):
            return ticker[: -len(quote_symbol)], quote_symbol
    return None, None


def _upsert_instruments_for_products(
    session,
    *,
    venue: str,
    product_ids: set[str],
    updated_at: datetime,
) -> None:
    if not product_ids:
        return

    existing_by_product = {
        row.product_id: row
        for row in (
            session.query(MarketInstrumentRegistry)
            .filter_by(venue=venue)
            .filter(MarketInstrumentRegistry.product_id.in_(sorted(product_ids)))
            .all()
        )
    }
    for product_id in sorted(product_ids):
        base_symbol, quote_symbol = _infer_symbols(product_id)
        existing = existing_by_product.get(product_id)
        if existing is not None:
            existing.base_symbol = existing.base_symbol or base_symbol
            existing.quote_symbol = existing.quote_symbol or quote_symbol
            existing.product_type = existing.product_type or "SPOT"
            existing.status = existing.status or "active"
            existing.updated_at = updated_at
            continue
        session.add(
            MarketInstrumentRegistry(
                venue=venue,
                product_id=product_id,
                base_symbol=base_symbol,
                quote_symbol=quote_symbol,
                product_type="SPOT",
                status="active",
                price_increment="",
                base_increment="",
                quote_increment="",
                first_seen_at=updated_at,
                updated_at=updated_at,
            )
        )


class MassiveNormalizer:
    """Normalize Massive market data into canonical truth tables."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def normalize_reference_tickers(
        self,
        tickers: list[dict],
        *,
        venue: str = "massive",
    ) -> int:
        """Upsert Massive ticker reference rows into market_instrument_registry."""
        if not tickers:
            return 0

        session = get_session(self.settings)
        now = utcnow()
        count = 0
        try:
            for row in tickers:
                if not isinstance(row, dict):
                    continue
                product_id = str(row.get("ticker") or "").strip()
                if not product_id:
                    continue
                base_symbol = row.get("base_currency_symbol") or row.get("base_symbol")
                quote_symbol = row.get("quote_currency_symbol") or row.get("quote_symbol")
                if not base_symbol or not quote_symbol:
                    inferred_base, inferred_quote = _infer_symbols(product_id)
                    base_symbol = base_symbol or inferred_base
                    quote_symbol = quote_symbol or inferred_quote

                existing = (
                    session.query(MarketInstrumentRegistry)
                    .filter_by(venue=venue, product_id=product_id)
                    .first()
                )
                status = row.get("status")
                if status is None and "active" in row:
                    status = "active" if row.get("active") else "inactive"

                if existing:
                    existing.base_symbol = base_symbol
                    existing.quote_symbol = quote_symbol
                    existing.product_type = row.get("market") or row.get("type")
                    existing.status = status
                    existing.updated_at = now
                else:
                    session.add(
                        MarketInstrumentRegistry(
                            venue=venue,
                            product_id=product_id,
                            base_symbol=base_symbol,
                            quote_symbol=quote_symbol,
                            product_type=row.get("market") or row.get("type"),
                            status=status,
                            price_increment=str(row.get("tick_size") or ""),
                            base_increment=str(row.get("min_trade_size") or ""),
                            quote_increment=str(row.get("quote_increment") or ""),
                            first_seen_at=now,
                            updated_at=now,
                        )
                    )
                count += 1

            session.commit()
            return count
        finally:
            session.close()

    def normalize_snapshot(
        self,
        snapshot: dict,
        ingest_run_id: str,
        *,
        venue: str = "massive",
    ) -> int:
        """Normalize Massive snapshot bars into market_candle rows."""
        if not isinstance(snapshot, dict):
            return 0

        product_id = str(snapshot.get("ticker") or "").strip()
        if not product_id and isinstance(snapshot.get("ticker"), dict):
            product_id = str(snapshot["ticker"].get("ticker") or "").strip()
        if not product_id and isinstance(snapshot.get("results"), dict):
            product_id = str(snapshot["results"].get("ticker") or "").strip()
        if not product_id:
            return 0

        container = snapshot.get("ticker") if isinstance(snapshot.get("ticker"), dict) else snapshot
        captured_at = utcnow()
        rows_to_add: list[MarketCandle] = []
        for bar_key, granularity in (("min", "ONE_MINUTE"), ("day", "ONE_DAY")):
            bar = container.get(bar_key) or snapshot.get(bar_key)
            if not isinstance(bar, dict):
                continue
            start_time = _parse_epoch_any(bar.get("t") or bar.get("start"))
            fields = derive_event_time_fields(
                start_time,
                captured_at,
                str(bar.get("t") or bar.get("start") or ""),
            )
            rows_to_add.append(
                MarketCandle(
                    ingest_run_id=ingest_run_id,
                    venue=venue,
                    product_id=product_id,
                    granularity=granularity,
                    start_time_utc=start_time or captured_at,
                    end_time_utc=None,
                    open=_as_float(bar.get("o") or bar.get("open")),
                    high=_as_float(bar.get("h") or bar.get("high")),
                    low=_as_float(bar.get("l") or bar.get("low")),
                    close=_as_float(bar.get("c") or bar.get("close")),
                    volume=_as_float(bar.get("v") or bar.get("volume")),
                    source_event_time_utc=fields["source_event_time_utc"],
                    captured_at_utc=fields["captured_at_utc"],
                    source_time_raw=fields["source_time_raw"],
                    event_date_utc=fields["event_date_utc"],
                    hour_utc=fields["hour_utc"],
                    minute_of_day_utc=fields["minute_of_day_utc"],
                    weekday_utc=fields["weekday_utc"],
                    time_quality=fields["time_quality"],
                )
            )

        if not rows_to_add:
            return 0

        session = get_session(self.settings)
        try:
            session.add_all(rows_to_add)
            session.commit()
            return len(rows_to_add)
        finally:
            session.close()

    def normalize_minute_aggs(
        self,
        rows: list[dict[str, str]],
        ingest_run_id: str,
        *,
        venue: str = "massive",
        allowed_tickers: list[str] | None = None,
    ) -> int:
        """Normalize Massive minute-aggregate rows into market_candle."""
        if not rows:
            return 0

        allowed_ticker_set = {
            str(ticker).upper()
            for ticker in (allowed_tickers or self.settings.massive_default_tickers)
            if str(ticker).strip()
        }
        session = get_session(self.settings)
        captured_at = utcnow()
        count = 0
        seen_product_ids: set[str] = set()
        try:
            for row in rows:
                product_id = str(row.get("ticker") or row.get("T") or "").strip()
                if not product_id:
                    continue
                if allowed_ticker_set and product_id.upper() not in allowed_ticker_set:
                    continue
                seen_product_ids.add(product_id)
                start_time = _parse_epoch_any(
                    row.get("window_start")
                    or row.get("windowStart")
                    or row.get("t")
                )
                fields = derive_event_time_fields(
                    start_time,
                    captured_at,
                    str(row.get("window_start") or row.get("windowStart") or row.get("t") or ""),
                )
                session.add(
                    MarketCandle(
                        ingest_run_id=ingest_run_id,
                        venue=venue,
                        product_id=product_id,
                        granularity="ONE_MINUTE",
                        start_time_utc=start_time or captured_at,
                        end_time_utc=None,
                        open=_as_float(row.get("open") or row.get("o")),
                        high=_as_float(row.get("high") or row.get("h")),
                        low=_as_float(row.get("low") or row.get("l")),
                        close=_as_float(row.get("close") or row.get("c")),
                        volume=_as_float(row.get("volume") or row.get("v")),
                        source_event_time_utc=fields["source_event_time_utc"],
                        captured_at_utc=fields["captured_at_utc"],
                        source_time_raw=fields["source_time_raw"],
                        event_date_utc=fields["event_date_utc"],
                        hour_utc=fields["hour_utc"],
                        minute_of_day_utc=fields["minute_of_day_utc"],
                        weekday_utc=fields["weekday_utc"],
                        time_quality=fields["time_quality"],
                    )
                )
                count += 1

            _upsert_instruments_for_products(
                session,
                venue=venue,
                product_ids=seen_product_ids,
                updated_at=captured_at,
            )
            session.commit()
            return count
        finally:
            session.close()
