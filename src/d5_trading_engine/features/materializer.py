"""Deterministic feature materialization for the first bounded feature set."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta

import orjson

from d5_trading_engine.common.errors import FeatureError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    FeatureMaterializationRun,
    FeatureSpotChainMacroMinuteV1,
    FredObservation,
    IngestRun,
    MarketCandle,
    MarketInstrumentRegistry,
    MarketTradeEvent,
    OrderBookL2Event,
    QuoteSnapshot,
    SolanaAddressRegistry,
    SolanaTransferEvent,
    SourceHealthEvent,
    TokenPriceSnapshot,
    TokenRegistry,
)

log = get_logger(__name__, feature_set="spot_chain_macro_v1")

_FEATURE_SET_NAME = "spot_chain_macro_v1"
_SOURCE_TABLES = [
    "token_price_snapshot",
    "quote_snapshot",
    "token_registry",
    "market_instrument_registry",
    "market_candle",
    "market_trade_event",
    "order_book_l2_event",
    "solana_transfer_event",
    "solana_address_registry",
    "program_registry",
    "fred_observation",
    "ingest_run",
    "source_health_event",
]
_FRED_SERIES_FIELDS = {
    "DFF": "fred_dff",
    "T10Y2Y": "fred_t10y2y",
    "VIXCLS": "fred_vixcls",
    "DGS10": "fred_dgs10",
    "DTWEXBGS": "fred_dtwexbgs",
}
_DEGRADED_RATIO = 0.8
_REQUIRED_LANES = (
    "jupiter-prices",
    "jupiter-quotes",
    "helius-transactions",
    "coinbase-products",
    "coinbase-candles",
    "coinbase-market-trades",
    "coinbase-book",
    "fred-observations",
)
_FRESHNESS_RULES = {
    "jupiter-prices": {
        "provider": "jupiter",
        "capture_type": "prices",
        "expectation_class": "recurring_market_snapshot",
        "window": timedelta(minutes=15),
    },
    "jupiter-quotes": {
        "provider": "jupiter",
        "capture_type": "quotes",
        "expectation_class": "recurring_market_snapshot",
        "window": timedelta(minutes=15),
    },
    "helius-transactions": {
        "provider": "helius",
        "capture_type": "enhanced_transactions",
        "expectation_class": "recurring_chain_state_pull",
        "window": timedelta(minutes=30),
    },
    "coinbase-products": {
        "provider": "coinbase",
        "capture_type": "products",
        "expectation_class": "reference_refresh",
        "window": timedelta(hours=24),
    },
    "coinbase-candles": {
        "provider": "coinbase",
        "capture_type": "candles",
        "expectation_class": "recurring_market_data_lane",
        "window": timedelta(minutes=30),
    },
    "coinbase-market-trades": {
        "provider": "coinbase",
        "capture_type": "market_trades",
        "expectation_class": "recurring_market_data_lane",
        "window": timedelta(minutes=30),
    },
    "coinbase-book": {
        "provider": "coinbase",
        "capture_type": "book",
        "expectation_class": "recurring_market_data_lane",
        "window": timedelta(minutes=30),
    },
    "fred-observations": {
        "provider": "fred",
        "capture_type": "observations",
        "expectation_class": "slower_macro_lane",
        "window": timedelta(days=2),
    },
}


def _minute_bucket(dt: datetime | None) -> datetime | None:
    normalized = ensure_utc(dt)
    if normalized is None:
        return None
    return normalized.replace(second=0, microsecond=0)


def _minute_fields(dt: datetime) -> dict[str, datetime | str | int]:
    normalized = ensure_utc(dt)
    assert normalized is not None
    return {
        "feature_minute_utc": normalized,
        "event_date_utc": normalized.strftime("%Y-%m-%d"),
        "hour_utc": normalized.hour,
        "minute_of_day_utc": (normalized.hour * 60) + normalized.minute,
        "weekday_utc": normalized.weekday(),
    }


def _safe_mean(total: float, count: int) -> float | None:
    if count <= 0:
        return None
    return total / count


def _isoformat(dt: datetime | None) -> str | None:
    normalized = ensure_utc(dt)
    if normalized is None:
        return None
    return normalized.isoformat()


class FeatureMaterializer:
    """Materialize deterministic feature tables from canonical truth."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _start_feature_run(
        self,
        run_id: str,
        feature_set: str,
        source_tables: list[str],
    ) -> None:
        now = utcnow()
        session = get_session(self.settings)
        try:
            session.add(
                FeatureMaterializationRun(
                    run_id=run_id,
                    feature_set=feature_set,
                    source_tables=orjson.dumps(source_tables).decode(),
                    status="running",
                    started_at=now,
                    created_at=now,
                )
            )
            session.commit()
        finally:
            session.close()

    def _finish_feature_run(
        self,
        run_id: str,
        *,
        status: str,
        row_count: int = 0,
        error: str | None = None,
        freshness_snapshot: dict[str, object] | None = None,
        input_window_start_utc: datetime | None = None,
        input_window_end_utc: datetime | None = None,
    ) -> None:
        session = get_session(self.settings)
        try:
            run = session.query(FeatureMaterializationRun).filter_by(run_id=run_id).first()
            if run is not None:
                run.status = status
                run.row_count = row_count
                run.finished_at = utcnow()
                run.error_message = error
                if freshness_snapshot is not None:
                    run.freshness_snapshot_json = orjson.dumps(freshness_snapshot).decode()
                run.input_window_start_utc = ensure_utc(input_window_start_utc)
                run.input_window_end_utc = ensure_utc(input_window_end_utc)
                session.commit()
        finally:
            session.close()

    def _authorize_required_lanes(self) -> dict[str, object]:
        now = utcnow()
        session = get_session(self.settings)
        try:
            lane_by_receipt = {
                (rule["provider"], rule["capture_type"]): lane_name
                for lane_name, rule in _FRESHNESS_RULES.items()
            }
            providers = sorted({rule["provider"] for rule in _FRESHNESS_RULES.values()})
            capture_types = sorted(
                {rule["capture_type"] for rule in _FRESHNESS_RULES.values()}
            )
            latest_success_by_lane: dict[str, IngestRun] = {}
            latest_failure_by_lane: dict[str, IngestRun] = {}
            for run in (
                session.query(IngestRun)
                .filter(IngestRun.provider.in_(providers))
                .filter(IngestRun.capture_type.in_(capture_types))
                .order_by(IngestRun.finished_at.desc(), IngestRun.started_at.desc())
                .all()
            ):
                lane_name = lane_by_receipt.get((run.provider, run.capture_type))
                if lane_name is None:
                    continue
                if run.status == "success" and lane_name not in latest_success_by_lane:
                    latest_success_by_lane[lane_name] = run
                elif run.status != "success" and lane_name not in latest_failure_by_lane:
                    latest_failure_by_lane[lane_name] = run

            latest_health_by_provider: dict[str, SourceHealthEvent] = {}
            providers = sorted({rule["provider"] for rule in _FRESHNESS_RULES.values()})
            for event in (
                session.query(SourceHealthEvent)
                .filter(SourceHealthEvent.provider.in_(providers))
                .order_by(SourceHealthEvent.checked_at.desc())
                .all()
            ):
                if event.provider not in latest_health_by_provider:
                    latest_health_by_provider[event.provider] = event
        finally:
            session.close()

        lane_states: dict[str, dict[str, object]] = {}
        blocking_lanes: list[str] = []
        for capture_type in _REQUIRED_LANES:
            rule = _FRESHNESS_RULES[capture_type]
            success = latest_success_by_lane.get(capture_type)
            failure = latest_failure_by_lane.get(capture_type)
            health = latest_health_by_provider.get(rule["provider"])
            window = rule["window"]

            if success is None:
                freshness_state = "never_started"
            else:
                success_time = ensure_utc(success.finished_at or success.started_at)
                assert success_time is not None
                age = now - success_time
                health_missing = health is None
                health_failed = health is not None and not bool(health.is_healthy)
                if age > window:
                    freshness_state = "stale"
                elif health_missing or health_failed or age > (window * _DEGRADED_RATIO):
                    freshness_state = "degraded"
                else:
                    freshness_state = "healthy_recent"

            downstream_eligible = freshness_state == "healthy_recent"
            latest_error_summary = None
            if failure is not None and failure.error_message:
                latest_error_summary = failure.error_message
            elif health is not None and health.error_message:
                latest_error_summary = health.error_message
            elif freshness_state == "never_started":
                latest_error_summary = "no successful baseline receipt"
            elif health is None:
                latest_error_summary = "missing provider health receipt"

            lane_states[capture_type] = {
                "provider": rule["provider"],
                "capture_type": rule["capture_type"],
                "expectation_class": rule["expectation_class"],
                "freshness_window_minutes": int(window.total_seconds() // 60),
                "last_success_at_utc": _isoformat(
                    success.finished_at or success.started_at if success else None
                ),
                "last_failure_at_utc": _isoformat(
                    failure.finished_at or failure.started_at if failure else None
                ),
                "latest_health_at_utc": _isoformat(health.checked_at if health else None),
                "freshness_state": freshness_state,
                "downstream_eligible": downstream_eligible,
                "latest_error_summary": latest_error_summary,
            }
            if not downstream_eligible:
                blocking_lanes.append(f"{capture_type}={freshness_state}")

        snapshot = {
            "generated_at_utc": _isoformat(now),
            "required_lanes": lane_states,
            "authorized": not blocking_lanes,
            "blocking_lanes": blocking_lanes,
        }
        return snapshot

    def materialize_spot_chain_macro_v1(self) -> tuple[str, int]:
        """Materialize the first bounded minute-by-mint feature table."""
        run_id = f"feature_{_FEATURE_SET_NAME}_{uuid.uuid4().hex[:12]}"
        self._start_feature_run(run_id, _FEATURE_SET_NAME, _SOURCE_TABLES)

        freshness_snapshot: dict[str, object] | None = None
        try:
            freshness_snapshot = self._authorize_required_lanes()
            if freshness_snapshot["blocking_lanes"]:
                joined = ", ".join(freshness_snapshot["blocking_lanes"])
                raise FeatureError(f"Freshness authorization failed: {joined}")
            rows = self._build_spot_chain_macro_rows(run_id)
            if not rows:
                raise FeatureError(
                    "No eligible feature rows were materialized from canonical truth."
                )

            session = get_session(self.settings)
            try:
                session.add_all(rows)
                session.commit()
            finally:
                session.close()

            feature_minutes = [row.feature_minute_utc for row in rows]
            self._finish_feature_run(
                run_id,
                status="success",
                row_count=len(rows),
                freshness_snapshot=freshness_snapshot,
                input_window_start_utc=min(feature_minutes),
                input_window_end_utc=max(feature_minutes),
            )
            log.info("feature_materialization_complete", run_id=run_id, row_count=len(rows))
            return run_id, len(rows)
        except Exception as exc:
            self._finish_feature_run(
                run_id,
                status="failed",
                error=str(exc),
                freshness_snapshot=freshness_snapshot,
            )
            raise

    def _build_spot_chain_macro_rows(self, run_id: str) -> list[FeatureSpotChainMacroMinuteV1]:
        session = get_session(self.settings)
        created_at = utcnow()
        tracked_mints = set(self.settings.token_universe)
        usdc_mint = next(
            (mint for mint, symbol in self.settings.token_symbol_hints.items() if symbol == "USDC"),
            None,
        )
        try:
            symbol_by_mint = dict(self.settings.token_symbol_hints)
            for registry_row in (
                session.query(TokenRegistry)
                .filter(TokenRegistry.mint.in_(tracked_mints))
                .all()
            ):
                if registry_row.symbol:
                    symbol_by_mint[registry_row.mint] = registry_row.symbol

            price_rows = (
                session.query(TokenPriceSnapshot)
                .filter(TokenPriceSnapshot.mint.in_(tracked_mints))
                .order_by(TokenPriceSnapshot.captured_at.asc())
                .all()
            )
            price_buckets: dict[tuple[str, datetime], TokenPriceSnapshot] = {}
            for row in price_rows:
                minute = _minute_bucket(row.captured_at)
                if minute is None:
                    continue
                symbol_by_mint[row.mint] = row.symbol or symbol_by_mint.get(row.mint)
                price_buckets[(row.mint, minute)] = row

            if not price_buckets:
                return []

            instrument_rows = (
                session.query(MarketInstrumentRegistry)
                .filter_by(venue="coinbase")
                .all()
            )
            product_by_symbol: dict[str, str] = {}
            for instrument in sorted(
                instrument_rows,
                key=lambda item: (
                    0 if (item.quote_symbol or "").upper() == "USD" else 1,
                    0 if (item.status or "").lower() == "online" else 1,
                    item.product_id,
                ),
            ):
                if not instrument.base_symbol or instrument.base_symbol in product_by_symbol:
                    continue
                if (instrument.quote_symbol or "").upper() not in {"USD", "USDC"}:
                    continue
                product_by_symbol[instrument.base_symbol] = instrument.product_id

            product_ids = {product_id for product_id in product_by_symbol.values() if product_id}

            candle_by_key: dict[tuple[str, datetime], MarketCandle] = {}
            if product_ids:
                candle_rows = (
                    session.query(MarketCandle)
                    .filter(MarketCandle.product_id.in_(product_ids))
                    .order_by(MarketCandle.start_time_utc.asc())
                    .all()
                )
                for row in candle_rows:
                    if row.granularity not in {"ONE_MINUTE", "60", "60s"}:
                        continue
                    minute = _minute_bucket(row.start_time_utc)
                    if minute is None:
                        continue
                    candle_by_key[(row.product_id, minute)] = row

            trade_stats: dict[tuple[str, datetime], dict[str, float | int]] = defaultdict(
                lambda: {"count": 0, "size_sum": 0.0}
            )
            if product_ids:
                for row in (
                    session.query(MarketTradeEvent)
                    .filter(MarketTradeEvent.product_id.in_(product_ids))
                    .all()
                ):
                    minute = _minute_bucket(row.source_event_time_utc or row.captured_at_utc)
                    if minute is None:
                        continue
                    stats = trade_stats[(row.product_id, minute)]
                    stats["count"] += 1
                    stats["size_sum"] += float(row.size or 0.0)

            book_by_key: dict[tuple[str, datetime], OrderBookL2Event] = {}
            if product_ids:
                for row in (
                    session.query(OrderBookL2Event)
                    .filter(OrderBookL2Event.product_id.in_(product_ids))
                    .all()
                ):
                    minute = _minute_bucket(row.source_event_time_utc or row.captured_at_utc)
                    if minute is None:
                        continue
                    book_by_key[(row.product_id, minute)] = row

            quote_stats: dict[tuple[str, datetime], dict[str, float | int]] = defaultdict(
                lambda: {
                    "count": 0,
                    "impact_sum": 0.0,
                    "impact_count": 0,
                    "latency_sum": 0.0,
                    "latency_count": 0,
                }
            )
            for row in (
                session.query(QuoteSnapshot)
                .filter(
                    (QuoteSnapshot.input_mint.in_(tracked_mints))
                    | (QuoteSnapshot.output_mint.in_(tracked_mints))
                )
                .all()
            ):
                tracked_mint = self._tracked_mint_for_quote(
                    row.input_mint,
                    row.output_mint,
                    tracked_mints,
                    usdc_mint,
                )
                if tracked_mint is None:
                    continue
                minute = _minute_bucket(row.source_event_time_utc or row.captured_at)
                if minute is None:
                    continue
                stats = quote_stats[(tracked_mint, minute)]
                stats["count"] += 1
                if row.price_impact_pct is not None:
                    stats["impact_sum"] += float(row.price_impact_pct)
                    stats["impact_count"] += 1
                if row.response_latency_ms is not None:
                    stats["latency_sum"] += float(row.response_latency_ms)
                    stats["latency_count"] += 1

            tracked_addresses = {
                row.address
                for row in session.query(SolanaAddressRegistry).filter_by(is_tracked=1).all()
            }
            chain_stats: dict[tuple[str, datetime], dict[str, float | int]] = defaultdict(
                lambda: {"count": 0, "amount_in": 0.0, "amount_out": 0.0}
            )
            for row in (
                session.query(SolanaTransferEvent)
                .filter(SolanaTransferEvent.mint.in_(tracked_mints))
                .all()
            ):
                minute = _minute_bucket(row.source_event_time_utc or row.captured_at_utc)
                if minute is None:
                    continue
                stats = chain_stats[(row.mint, minute)]
                stats["count"] += 1
                amount = float(row.amount_float or 0.0)
                if row.destination_address in tracked_addresses:
                    stats["amount_in"] += amount
                if row.source_address in tracked_addresses:
                    stats["amount_out"] += amount

            fred_rows_by_series: dict[str, list[FredObservation]] = defaultdict(list)
            for row in (
                session.query(FredObservation)
                .filter(FredObservation.series_id.in_(list(_FRED_SERIES_FIELDS)))
                .order_by(FredObservation.observation_date.asc())
                .all()
            ):
                fred_rows_by_series[row.series_id].append(row)

            feature_rows: list[FeatureSpotChainMacroMinuteV1] = []
            for mint, minute in sorted(price_buckets):
                price_row = price_buckets[(mint, minute)]
                symbol = symbol_by_mint.get(mint)
                product_id = product_by_symbol.get(symbol or "")
                quote = quote_stats.get((mint, minute), {})
                chain = chain_stats.get((mint, minute), {})
                candle = candle_by_key.get((product_id, minute)) if product_id else None
                trades = trade_stats.get((product_id, minute), {}) if product_id else {}
                book = book_by_key.get((product_id, minute)) if product_id else None
                feature_values = self._fred_feature_values(
                    fred_rows_by_series,
                    minute.strftime("%Y-%m-%d"),
                )
                minute_fields = _minute_fields(minute)

                feature_rows.append(
                    FeatureSpotChainMacroMinuteV1(
                        feature_run_id=run_id,
                        mint=mint,
                        symbol=symbol,
                        coinbase_product_id=product_id,
                        jupiter_price_usd=price_row.price_usd,
                        quote_count=int(quote.get("count", 0)),
                        mean_quote_price_impact_pct=_safe_mean(
                            float(quote.get("impact_sum", 0.0)),
                            int(quote.get("impact_count", 0)),
                        ),
                        mean_quote_response_latency_ms=_safe_mean(
                            float(quote.get("latency_sum", 0.0)),
                            int(quote.get("latency_count", 0)),
                        ),
                        coinbase_close=candle.close if candle else None,
                        coinbase_trade_count=int(trades.get("count", 0)),
                        coinbase_trade_size_sum=(
                            float(trades["size_sum"]) if "size_sum" in trades else None
                        ),
                        coinbase_book_spread_bps=book.spread_bps if book else None,
                        chain_transfer_count=int(chain.get("count", 0)),
                        chain_amount_in=(
                            float(chain["amount_in"]) if "amount_in" in chain else None
                        ),
                        chain_amount_out=(
                            float(chain["amount_out"]) if "amount_out" in chain else None
                        ),
                        created_at=created_at,
                        **minute_fields,
                        **feature_values,
                    )
                )

            return feature_rows
        finally:
            session.close()

    def _fred_feature_values(
        self,
        fred_rows_by_series: dict[str, list[FredObservation]],
        target_date: str,
    ) -> dict[str, float | None]:
        values = {column_name: None for column_name in _FRED_SERIES_FIELDS.values()}
        for series_id, column_name in _FRED_SERIES_FIELDS.items():
            for row in fred_rows_by_series.get(series_id, []):
                if row.observation_date <= target_date:
                    values[column_name] = row.value
                else:
                    break
        return values

    @staticmethod
    def _tracked_mint_for_quote(
        input_mint: str,
        output_mint: str,
        tracked_mints: set[str],
        usdc_mint: str | None,
    ) -> str | None:
        if input_mint in tracked_mints and input_mint != usdc_mint:
            return input_mint
        if output_mint in tracked_mints and output_mint != usdc_mint:
            return output_mint
        if input_mint in tracked_mints:
            return input_mint
        if output_mint in tracked_mints:
            return output_mint
        return None
