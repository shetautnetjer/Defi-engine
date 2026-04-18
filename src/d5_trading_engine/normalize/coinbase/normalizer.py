"""Normalize Coinbase public market-data payloads into canonical truth tables."""

from __future__ import annotations

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import (
    derive_event_time_fields,
    from_iso,
    from_unix_timestamp,
    utcnow,
)
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    MarketCandle,
    MarketInstrumentRegistry,
    MarketTradeEvent,
    OrderBookL2Event,
)

log = get_logger(__name__, normalizer="coinbase")

_COINBASE_FUTURE_ROOT_ALIASES = {
    "CDEGLD": "GOLD",
    "CDEOIL": "CRUDEOIL",
}


def _as_float(value) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _derive_coinbase_future_base_symbol(product: dict, future_details: dict) -> str | None:
    root_unit = str(future_details.get("contract_root_unit") or "").upper()
    contract_code = str(future_details.get("contract_code") or "").upper()
    display_name = " ".join(
        str(value or "")
        for value in (
            product.get("display_name"),
            product.get("display_name_overwrite"),
            future_details.get("display_name"),
            future_details.get("group_description"),
            future_details.get("group_short_description"),
        )
    ).upper()

    if root_unit in _COINBASE_FUTURE_ROOT_ALIASES:
        return _COINBASE_FUTURE_ROOT_ALIASES[root_unit]
    if root_unit and root_unit.isalnum() and not root_unit.startswith("CDE"):
        return root_unit
    if contract_code == "GOL" or "GOLD" in display_name or "GLD" in display_name:
        return "GOLD"
    if contract_code == "NOL" or "CRUDE" in display_name or " OIL" in display_name:
        return "CRUDEOIL"
    return None


def derive_coinbase_product_metadata(product: dict) -> dict[str, str | None]:
    """Derive stable canonical metadata for Coinbase spot and futures products."""
    future_details = product.get("future_product_details") or {}
    product_type = str(product.get("product_type") or "").upper() or None
    base_symbol = (
        product.get("base_currency_id")
        or product.get("base_display_symbol")
        or _derive_coinbase_future_base_symbol(product, future_details)
    )
    quote_symbol = product.get("quote_currency_id") or product.get("quote_display_symbol") or None
    if product_type == "FUTURE" and not quote_symbol:
        quote_symbol = "USD"

    return {
        "base_symbol": str(base_symbol).upper() if base_symbol else None,
        "quote_symbol": str(quote_symbol).upper() if quote_symbol else None,
        "product_type": product_type,
        "product_venue": product.get("product_venue") or future_details.get("venue"),
        "contract_expiry_type": (
            product.get("contract_expiry_type") or future_details.get("contract_expiry_type")
        ),
        "futures_asset_type": future_details.get("futures_asset_type"),
        "contract_root_unit": future_details.get("contract_root_unit"),
        "status": product.get("status"),
        "price_increment": product.get("price_increment"),
        "base_increment": product.get("base_increment"),
        "quote_increment": product.get("quote_increment"),
    }


class CoinbaseNormalizer:
    """Normalize Coinbase market-data payloads."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def normalize_products(self, products: list[dict], venue: str = "coinbase") -> int:
        """Upsert Coinbase products into the market instrument registry."""
        if not products:
            return 0

        session = get_session(self.settings)
        now = utcnow()
        count = 0
        try:
            for product in products:
                if not isinstance(product, dict):
                    continue

                product_id = product.get("product_id") or product.get("productId")
                if not product_id:
                    continue

                existing = (
                    session.query(MarketInstrumentRegistry)
                    .filter_by(venue=venue, product_id=product_id)
                    .first()
                )
                metadata = derive_coinbase_product_metadata(product)
                if existing:
                    existing.base_symbol = metadata["base_symbol"]
                    existing.quote_symbol = metadata["quote_symbol"]
                    existing.product_type = metadata["product_type"]
                    existing.product_venue = metadata["product_venue"]
                    existing.contract_expiry_type = metadata["contract_expiry_type"]
                    existing.futures_asset_type = metadata["futures_asset_type"]
                    existing.contract_root_unit = metadata["contract_root_unit"]
                    existing.status = metadata["status"]
                    existing.price_increment = metadata["price_increment"]
                    existing.base_increment = metadata["base_increment"]
                    existing.quote_increment = metadata["quote_increment"]
                    existing.updated_at = now
                else:
                    session.add(
                        MarketInstrumentRegistry(
                            venue=venue,
                            product_id=product_id,
                            base_symbol=metadata["base_symbol"],
                            quote_symbol=metadata["quote_symbol"],
                            product_type=metadata["product_type"],
                            product_venue=metadata["product_venue"],
                            contract_expiry_type=metadata["contract_expiry_type"],
                            futures_asset_type=metadata["futures_asset_type"],
                            contract_root_unit=metadata["contract_root_unit"],
                            status=metadata["status"],
                            price_increment=metadata["price_increment"],
                            base_increment=metadata["base_increment"],
                            quote_increment=metadata["quote_increment"],
                            first_seen_at=now,
                            updated_at=now,
                        )
                    )
                count += 1

            session.commit()
            log.info("normalize_coinbase_products_complete", count=count)
            return count
        finally:
            session.close()

    def normalize_candles(
        self,
        product_id: str,
        candles: list[dict],
        ingest_run_id: str,
        venue: str = "coinbase",
    ) -> int:
        """Normalize candle rows into canonical market_candle."""
        if not candles:
            return 0

        session = get_session(self.settings)
        captured_at = utcnow()
        count = 0
        try:
            for candle in candles:
                if not isinstance(candle, dict):
                    continue

                start_time = from_unix_timestamp(candle.get("start"))
                fields = derive_event_time_fields(
                    start_time,
                    captured_at,
                    str(candle.get("start")) if candle.get("start") is not None else None,
                )
                session.add(
                    MarketCandle(
                        ingest_run_id=ingest_run_id,
                        venue=venue,
                        product_id=product_id,
                        granularity=str(candle.get("granularity", "ONE_MINUTE")),
                        start_time_utc=start_time or captured_at,
                        end_time_utc=None,
                        open=_as_float(candle.get("open")),
                        high=_as_float(candle.get("high")),
                        low=_as_float(candle.get("low")),
                        close=_as_float(candle.get("close")),
                        volume=_as_float(candle.get("volume")),
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

            session.commit()
            return count
        finally:
            session.close()

    def normalize_market_trades(
        self,
        product_id: str,
        trades: list[dict],
        ingest_run_id: str,
        venue: str = "coinbase",
    ) -> int:
        """Normalize trade payloads into canonical market_trade_event."""
        if not trades:
            return 0

        session = get_session(self.settings)
        captured_at = utcnow()
        count = 0
        try:
            for trade in trades:
                if not isinstance(trade, dict):
                    continue

                time_raw = trade.get("time")
                fields = derive_event_time_fields(
                    from_iso(time_raw) if time_raw else None,
                    captured_at,
                    time_raw,
                )
                session.add(
                    MarketTradeEvent(
                        ingest_run_id=ingest_run_id,
                        venue=venue,
                        product_id=product_id,
                        trade_id=str(trade.get("trade_id") or trade.get("tradeId") or ""),
                        side=trade.get("side"),
                        price=_as_float(trade.get("price")),
                        size=_as_float(trade.get("size")),
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

            session.commit()
            return count
        finally:
            session.close()

    def normalize_book_snapshot(
        self,
        product_id: str,
        book: dict,
        ingest_run_id: str,
        venue: str = "coinbase",
    ) -> int:
        """Normalize an order-book snapshot into canonical order_book_l2_event."""
        if not isinstance(book, dict):
            return 0

        session = get_session(self.settings)
        captured_at = utcnow()
        try:
            pricebook = book.get("pricebook", book)
            bids = pricebook.get("bids", [])
            asks = pricebook.get("asks", [])
            best_bid = _as_float(bids[0].get("price")) if bids else None
            best_ask = _as_float(asks[0].get("price")) if asks else None
            spread_absolute = None
            spread_bps = None
            if best_bid is not None and best_ask is not None and best_bid:
                spread_absolute = best_ask - best_bid
                spread_bps = ((best_ask - best_bid) / best_bid) * 10000

            fields = derive_event_time_fields(None, captured_at, None)
            session.add(
                OrderBookL2Event(
                    ingest_run_id=ingest_run_id,
                    venue=venue,
                    product_id=product_id,
                    event_kind="snapshot",
                    best_bid=best_bid,
                    best_ask=best_ask,
                    spread_absolute=spread_absolute,
                    spread_bps=spread_bps,
                    bids_json=orjson.dumps(bids).decode(),
                    asks_json=orjson.dumps(asks).decode(),
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
            session.commit()
            return 1
        finally:
            session.close()
