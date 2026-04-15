"""Deterministic feature materialization for bounded feature sets."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import fmean, pstdev

import orjson

from d5_trading_engine.common.errors import FeatureError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    FeatureGlobalRegimeInput15mV1,
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

_SPOT_CHAIN_FEATURE_SET_NAME = "spot_chain_macro_v1"
_GLOBAL_REGIME_FEATURE_SET_NAME = "global_regime_inputs_15m_v1"
_FEATURE_SET_NAME = _SPOT_CHAIN_FEATURE_SET_NAME

_SPOT_CHAIN_SOURCE_TABLES = [
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
_GLOBAL_REGIME_SOURCE_TABLES = [
    "market_instrument_registry",
    "market_candle",
    "market_trade_event",
    "order_book_l2_event",
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
_SPOT_CHAIN_REQUIRED_LANES = (
    "jupiter-prices",
    "jupiter-quotes",
    "helius-transactions",
    "coinbase-products",
    "coinbase-candles",
    "coinbase-market-trades",
    "coinbase-book",
    "fred-observations",
)
_GLOBAL_REGIME_REQUIRED_LANES = (
    "coinbase-products",
    "coinbase-candles",
    "coinbase-market-trades",
    "coinbase-book",
)
_GLOBAL_REGIME_OPTIONAL_LANES = ("fred-observations",)
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
_REGIME_PROXY_PREFERENCE = ("BTC", "ETH", "SOL")
_REGIME_BUCKET_MINUTES = 15
_FOUR_HOUR_BUCKET_COUNT = 16

log = get_logger(__name__)


def _minute_bucket(dt: datetime | None) -> datetime | None:
    normalized = ensure_utc(dt)
    if normalized is None:
        return None
    return normalized.replace(second=0, microsecond=0)


def _bucket_start(dt: datetime | None, bucket_minutes: int) -> datetime | None:
    minute = _minute_bucket(dt)
    if minute is None:
        return None
    floored_minute = minute.minute - (minute.minute % bucket_minutes)
    return minute.replace(minute=floored_minute)


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


def _bucket_fields(dt: datetime) -> dict[str, datetime | str | int]:
    normalized = ensure_utc(dt)
    assert normalized is not None
    return {
        "bucket_start_utc": normalized,
        "event_date_utc": normalized.strftime("%Y-%m-%d"),
        "hour_utc": normalized.hour,
        "minute_of_day_utc": (normalized.hour * 60) + normalized.minute,
        "weekday_utc": normalized.weekday(),
    }


def _safe_mean(total: float, count: int) -> float | None:
    if count <= 0:
        return None
    return total / count


def _series_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(fmean(values))


def _series_std(values: list[float]) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    return float(pstdev(values))


def _compound_return(values: list[float]) -> float | None:
    if not values:
        return None
    total = 1.0
    for value in values:
        total *= 1.0 + value
    return total - 1.0


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

    def _build_lane_snapshot(
        self,
        required_lanes: tuple[str, ...],
        optional_lanes: tuple[str, ...] = (),
    ) -> dict[str, object]:
        now = utcnow()
        lanes_to_check = tuple(dict.fromkeys(required_lanes + optional_lanes))
        session = get_session(self.settings)
        try:
            lane_by_receipt = {
                (rule["provider"], rule["capture_type"]): lane_name
                for lane_name, rule in _FRESHNESS_RULES.items()
                if lane_name in lanes_to_check
            }
            providers = sorted(
                {
                    rule["provider"]
                    for name, rule in _FRESHNESS_RULES.items()
                    if name in lanes_to_check
                }
            )
            capture_types = sorted(
                {
                    rule["capture_type"]
                    for name, rule in _FRESHNESS_RULES.items()
                    if name in lanes_to_check
                }
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
        for lane_name in lanes_to_check:
            rule = _FRESHNESS_RULES[lane_name]
            success = latest_success_by_lane.get(lane_name)
            failure = latest_failure_by_lane.get(lane_name)
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

            is_required = lane_name in required_lanes
            lane_states[lane_name] = {
                "provider": rule["provider"],
                "capture_type": rule["capture_type"],
                "expectation_class": rule["expectation_class"],
                "freshness_window_minutes": int(window.total_seconds() // 60),
                "required_for_authorization": is_required,
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
            if is_required and not downstream_eligible:
                blocking_lanes.append(f"{lane_name}={freshness_state}")

        return {
            "generated_at_utc": _isoformat(now),
            "required_lanes": lane_states,
            "authorized": not blocking_lanes,
            "blocking_lanes": blocking_lanes,
        }

    def materialize_spot_chain_macro_v1(self) -> tuple[str, int]:
        """Materialize the first bounded minute-by-mint feature table."""
        run_id = f"feature_{_SPOT_CHAIN_FEATURE_SET_NAME}_{uuid.uuid4().hex[:12]}"
        self._start_feature_run(run_id, _SPOT_CHAIN_FEATURE_SET_NAME, _SPOT_CHAIN_SOURCE_TABLES)

        freshness_snapshot: dict[str, object] | None = None
        try:
            freshness_snapshot = self._build_lane_snapshot(_SPOT_CHAIN_REQUIRED_LANES)
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
            log.info(
                "feature_materialization_complete",
                feature_set=_SPOT_CHAIN_FEATURE_SET_NAME,
                run_id=run_id,
                row_count=len(rows),
            )
            return run_id, len(rows)
        except Exception as exc:
            self._finish_feature_run(
                run_id,
                status="failed",
                error=str(exc),
                freshness_snapshot=freshness_snapshot,
            )
            raise

    def materialize_global_regime_inputs_15m_v1(self) -> tuple[str, int]:
        """Materialize market-wide 15-minute regime inputs."""
        run_id = f"feature_{_GLOBAL_REGIME_FEATURE_SET_NAME}_{uuid.uuid4().hex[:12]}"
        self._start_feature_run(
            run_id,
            _GLOBAL_REGIME_FEATURE_SET_NAME,
            _GLOBAL_REGIME_SOURCE_TABLES,
        )

        freshness_snapshot: dict[str, object] | None = None
        try:
            freshness_snapshot = self._build_lane_snapshot(
                _GLOBAL_REGIME_REQUIRED_LANES,
                _GLOBAL_REGIME_OPTIONAL_LANES,
            )
            if freshness_snapshot["blocking_lanes"]:
                joined = ", ".join(freshness_snapshot["blocking_lanes"])
                raise FeatureError(f"Freshness authorization failed: {joined}")
            rows = self._build_global_regime_rows(run_id)
            if not rows:
                raise FeatureError(
                    "No eligible global regime rows were materialized from canonical truth."
                )

            session = get_session(self.settings)
            try:
                session.add_all(rows)
                session.commit()
            finally:
                session.close()

            bucket_times = [row.bucket_start_utc for row in rows]
            self._finish_feature_run(
                run_id,
                status="success",
                row_count=len(rows),
                freshness_snapshot=freshness_snapshot,
                input_window_start_utc=min(bucket_times),
                input_window_end_utc=max(bucket_times),
            )
            log.info(
                "feature_materialization_complete",
                feature_set=_GLOBAL_REGIME_FEATURE_SET_NAME,
                run_id=run_id,
                row_count=len(rows),
            )
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
                .order_by(
                    FredObservation.observation_date.asc(),
                    FredObservation.captured_at.asc(),
                )
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
                    bucket_end_utc=minute + timedelta(minutes=1),
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

    def _build_global_regime_rows(self, run_id: str) -> list[FeatureGlobalRegimeInput15mV1]:
        session = get_session(self.settings)
        created_at = utcnow()
        try:
            proxy_products = self._select_regime_proxy_products(
                session.query(MarketInstrumentRegistry).filter_by(venue="coinbase").all()
            )
            if not proxy_products:
                return []

            product_ids = list(proxy_products.values())
            bucket_stats = self._aggregate_regime_market_stats(session, product_ids)
            if not bucket_stats:
                return []

            fred_rows_by_series: dict[str, list[FredObservation]] = defaultdict(list)
            for row in (
                session.query(FredObservation)
                .filter(FredObservation.series_id.in_(list(_FRED_SERIES_FIELDS)))
                .order_by(
                    FredObservation.observation_date.asc(),
                    FredObservation.captured_at.asc(),
                )
                .all()
            ):
                fred_rows_by_series[row.series_id].append(row)

            aggregate_rows: list[dict[str, object]] = []
            sorted_buckets = sorted(
                {
                    bucket
                    for (_, bucket) in bucket_stats["candles"]
                }
            )
            aggregate_returns: list[float] = []
            for bucket in sorted_buckets:
                product_returns: list[float] = []
                product_realized_vols: list[float] = []
                product_volumes: list[float] = []
                trade_counts: list[int] = []
                trade_sizes: list[float] = []
                spread_values: list[float] = []
                included_products: list[str] = []

                for product_id in product_ids:
                    candle_entry = bucket_stats["candles"].get((product_id, bucket))
                    if candle_entry is None or candle_entry["close"] is None:
                        continue
                    included_products.append(product_id)
                    if candle_entry["return_15m"] is not None:
                        product_returns.append(float(candle_entry["return_15m"]))
                    if candle_entry["realized_vol_15m"] is not None:
                        product_realized_vols.append(float(candle_entry["realized_vol_15m"]))
                    product_volumes.append(float(candle_entry["volume_sum"]))

                    trade_entry = bucket_stats["trades"].get((product_id, bucket))
                    if trade_entry is not None:
                        trade_counts.append(int(trade_entry["count"]))
                        trade_sizes.append(float(trade_entry["size_sum"]))

                    book_entry = bucket_stats["books"].get((product_id, bucket))
                    if book_entry is not None and book_entry["spread_mean"] is not None:
                        spread_values.append(float(book_entry["spread_mean"]))

                if not included_products:
                    continue

                aggregate_return = _series_mean(product_returns)
                aggregate_rows.append(
                    {
                        "bucket": bucket,
                        "proxy_products": included_products,
                        "market_return_mean_15m": aggregate_return,
                        "market_return_std_15m": _series_std(product_returns),
                        "market_realized_vol_15m": _series_mean(product_realized_vols),
                        "market_volume_sum_15m": sum(product_volumes) if product_volumes else None,
                        "market_trade_count_15m": sum(trade_counts),
                        "market_trade_size_sum_15m": sum(trade_sizes) if trade_sizes else None,
                        "market_book_spread_bps_mean_15m": _series_mean(spread_values),
                    }
                )
                if aggregate_return is not None:
                    aggregate_returns.append(float(aggregate_return))
                else:
                    aggregate_returns.append(0.0)

            feature_rows: list[FeatureGlobalRegimeInput15mV1] = []
            recent_returns: list[float] = []
            for row in aggregate_rows:
                recent_returns.append(float(row["market_return_mean_15m"] or 0.0))
                if len(recent_returns) > _FOUR_HOUR_BUCKET_COUNT:
                    recent_returns.pop(0)

                macro_values = self._fred_feature_values(
                    fred_rows_by_series,
                    row["bucket"].strftime("%Y-%m-%d"),
                    bucket_end_utc=row["bucket"] + timedelta(minutes=_REGIME_BUCKET_MINUTES),
                )
                macro_available = any(value is not None for value in macro_values.values())

                feature_rows.append(
                    FeatureGlobalRegimeInput15mV1(
                        feature_run_id=run_id,
                        regime_key="global",
                        proxy_products_json=orjson.dumps(sorted(row["proxy_products"])).decode(),
                        proxy_count=len(row["proxy_products"]),
                        market_return_mean_15m=row["market_return_mean_15m"],
                        market_return_std_15m=row["market_return_std_15m"],
                        market_realized_vol_15m=row["market_realized_vol_15m"],
                        market_volume_sum_15m=row["market_volume_sum_15m"],
                        market_trade_count_15m=row["market_trade_count_15m"],
                        market_trade_size_sum_15m=row["market_trade_size_sum_15m"],
                        market_book_spread_bps_mean_15m=row["market_book_spread_bps_mean_15m"],
                        market_return_mean_4h=_compound_return(recent_returns),
                        market_realized_vol_4h=_series_std(recent_returns),
                        macro_context_available=1 if macro_available else 0,
                        created_at=created_at,
                        **macro_values,
                        **_bucket_fields(row["bucket"]),
                    )
                )

            return feature_rows
        finally:
            session.close()

    def _aggregate_regime_market_stats(
        self,
        session,
        product_ids: list[str],
    ) -> dict[str, dict[tuple[str, datetime], dict[str, float | int | None]]]:
        candle_buckets: dict[tuple[str, datetime], dict[str, object]] = defaultdict(
            lambda: {
                "open": None,
                "close": None,
                "volume_sum": 0.0,
                "prev_close": None,
                "minute_returns": [],
            }
        )
        for row in (
            session.query(MarketCandle)
            .filter(MarketCandle.product_id.in_(product_ids))
            .order_by(MarketCandle.product_id.asc(), MarketCandle.start_time_utc.asc())
            .all()
        ):
            if row.granularity not in {"ONE_MINUTE", "60", "60s"}:
                continue
            bucket = _bucket_start(row.start_time_utc, _REGIME_BUCKET_MINUTES)
            if bucket is None:
                continue
            key = (row.product_id, bucket)
            stats = candle_buckets[key]
            open_value = float(row.open or row.close or 0.0)
            close_value = float(row.close or row.open or 0.0)
            if stats["open"] is None:
                stats["open"] = open_value
            prev_close = stats["prev_close"]
            if prev_close not in (None, 0.0) and close_value:
                stats["minute_returns"].append((close_value / float(prev_close)) - 1.0)
            stats["prev_close"] = close_value
            stats["close"] = close_value
            stats["volume_sum"] += float(row.volume or 0.0)

        finalized_candles: dict[tuple[str, datetime], dict[str, float | None]] = {}
        for key, stats in candle_buckets.items():
            open_value = stats["open"]
            close_value = stats["close"]
            return_15m = None
            if open_value not in (None, 0.0) and close_value is not None:
                return_15m = (float(close_value) / float(open_value)) - 1.0
            finalized_candles[key] = {
                "close": float(close_value) if close_value is not None else None,
                "return_15m": return_15m,
                "realized_vol_15m": _series_std(list(stats["minute_returns"])),
                "volume_sum": float(stats["volume_sum"]),
            }

        trade_buckets: dict[tuple[str, datetime], dict[str, float | int]] = defaultdict(
            lambda: {"count": 0, "size_sum": 0.0}
        )
        for row in (
            session.query(MarketTradeEvent)
            .filter(MarketTradeEvent.product_id.in_(product_ids))
            .all()
        ):
            bucket = _bucket_start(
                row.source_event_time_utc or row.captured_at_utc,
                _REGIME_BUCKET_MINUTES,
            )
            if bucket is None:
                continue
            entry = trade_buckets[(row.product_id, bucket)]
            entry["count"] += 1
            entry["size_sum"] += float(row.size or 0.0)

        book_buckets: dict[tuple[str, datetime], dict[str, float | int | None]] = defaultdict(
            lambda: {"spread_sum": 0.0, "count": 0, "spread_mean": None}
        )
        for row in (
            session.query(OrderBookL2Event)
            .filter(OrderBookL2Event.product_id.in_(product_ids))
            .all()
        ):
            bucket = _bucket_start(
                row.source_event_time_utc or row.captured_at_utc,
                _REGIME_BUCKET_MINUTES,
            )
            if bucket is None:
                continue
            entry = book_buckets[(row.product_id, bucket)]
            if row.spread_bps is not None:
                entry["spread_sum"] += float(row.spread_bps)
                entry["count"] += 1

        finalized_books: dict[tuple[str, datetime], dict[str, float | None]] = {}
        for key, stats in book_buckets.items():
            finalized_books[key] = {
                "spread_mean": _safe_mean(float(stats["spread_sum"]), int(stats["count"])),
            }

        return {
            "candles": finalized_candles,
            "trades": trade_buckets,
            "books": finalized_books,
        }

    def _select_regime_proxy_products(
        self,
        instruments: list[MarketInstrumentRegistry],
    ) -> dict[str, str]:
        product_by_symbol: dict[str, str] = {}
        for instrument in sorted(
            instruments,
            key=lambda item: (
                0 if (item.quote_symbol or "").upper() == "USD" else 1,
                0 if (item.status or "").lower() == "online" else 1,
                item.product_id,
            ),
        ):
            base_symbol = (instrument.base_symbol or "").upper()
            quote_symbol = (instrument.quote_symbol or "").upper()
            if not base_symbol or base_symbol in product_by_symbol:
                continue
            if quote_symbol not in {"USD", "USDC"}:
                continue
            product_by_symbol[base_symbol] = instrument.product_id

        selected: dict[str, str] = {}
        for symbol in _REGIME_PROXY_PREFERENCE:
            if symbol in product_by_symbol:
                selected[symbol] = product_by_symbol[symbol]
        if selected:
            return selected

        for symbol, product_id in product_by_symbol.items():
            selected[symbol] = product_id
            if len(selected) == len(_REGIME_PROXY_PREFERENCE):
                break
        return selected

    def _fred_feature_values(
        self,
        fred_rows_by_series: dict[str, list[FredObservation]],
        target_date: str,
        *,
        bucket_end_utc,
    ) -> dict[str, float | None]:
        values = {column_name: None for column_name in _FRED_SERIES_FIELDS.values()}
        bucket_end = ensure_utc(bucket_end_utc)
        for series_id, column_name in _FRED_SERIES_FIELDS.items():
            for row in fred_rows_by_series.get(series_id, []):
                captured_at = ensure_utc(row.captured_at)
                if (
                    row.observation_date <= target_date
                    and captured_at is not None
                    and captured_at <= bucket_end
                ):
                    values[column_name] = row.value
                else:
                    if row.observation_date > target_date:
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
