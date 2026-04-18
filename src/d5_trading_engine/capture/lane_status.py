"""Shared capture-lane freshness and operator status derivation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import IngestRun, RawHeliusWsEvent, SourceHealthEvent

_DEGRADED_RATIO = 0.8


@dataclass(frozen=True, slots=True)
class CaptureLaneRule:
    """Repo-owned freshness doctrine for one capture lane."""

    provider: str
    capture_type: str
    expectation_class: str
    freshness_window: timedelta
    health_endpoint_suffixes: tuple[str, ...] = ()
    readiness_only: bool = False
    uses_raw_receipt_presence: bool = False


CAPTURE_LANE_RULES: dict[str, CaptureLaneRule] = {
    "jupiter-tokens": CaptureLaneRule(
        provider="jupiter",
        capture_type="tokens",
        expectation_class="operator_reference_refresh",
        freshness_window=timedelta(hours=24),
        health_endpoint_suffixes=("/tokens/v2",),
    ),
    "jupiter-prices": CaptureLaneRule(
        provider="jupiter",
        capture_type="prices",
        expectation_class="recurring_market_snapshot",
        freshness_window=timedelta(minutes=15),
        health_endpoint_suffixes=("/price/v3", "/price/v2"),
    ),
    "jupiter-quotes": CaptureLaneRule(
        provider="jupiter",
        capture_type="quotes",
        expectation_class="recurring_market_snapshot",
        freshness_window=timedelta(minutes=15),
        health_endpoint_suffixes=("/swap/v1/quote", "/quote"),
    ),
    "helius-transactions": CaptureLaneRule(
        provider="helius",
        capture_type="enhanced_transactions",
        expectation_class="recurring_chain_state_pull",
        freshness_window=timedelta(minutes=30),
        health_endpoint_suffixes=("/transactions",),
    ),
    "helius-discovery": CaptureLaneRule(
        provider="helius",
        capture_type="account_discovery",
        expectation_class="discovery_backfill_refresh",
        freshness_window=timedelta(hours=24),
        health_endpoint_suffixes=("getaccountinfo",),
    ),
    "helius-ws-events": CaptureLaneRule(
        provider="helius",
        capture_type="ws_events",
        expectation_class="bounded_stream_receipt_lane",
        freshness_window=timedelta(minutes=15),
        health_endpoint_suffixes=("transactionsubscribe",),
        uses_raw_receipt_presence=True,
    ),
    "coinbase-products": CaptureLaneRule(
        provider="coinbase",
        capture_type="products",
        expectation_class="reference_refresh",
        freshness_window=timedelta(hours=24),
        health_endpoint_suffixes=("/market/products", "/products"),
    ),
    "coinbase-candles": CaptureLaneRule(
        provider="coinbase",
        capture_type="candles",
        expectation_class="recurring_market_data_lane",
        freshness_window=timedelta(minutes=30),
        health_endpoint_suffixes=("/candles",),
    ),
    "coinbase-market-trades": CaptureLaneRule(
        provider="coinbase",
        capture_type="market_trades",
        expectation_class="recurring_market_data_lane",
        freshness_window=timedelta(minutes=30),
        health_endpoint_suffixes=("/ticker", "/trades"),
    ),
    "coinbase-book": CaptureLaneRule(
        provider="coinbase",
        capture_type="book",
        expectation_class="recurring_market_data_lane",
        freshness_window=timedelta(minutes=30),
        health_endpoint_suffixes=("/product_book", "product_book"),
    ),
    "fred-series": CaptureLaneRule(
        provider="fred",
        capture_type="series",
        expectation_class="operator_reference_refresh",
        freshness_window=timedelta(days=7),
        health_endpoint_suffixes=("series_info", "/series"),
    ),
    "fred-observations": CaptureLaneRule(
        provider="fred",
        capture_type="observations",
        expectation_class="slower_macro_lane",
        freshness_window=timedelta(days=2),
        health_endpoint_suffixes=("/observations", "observations"),
    ),
    "massive-crypto": CaptureLaneRule(
        provider="massive",
        capture_type="crypto_reference",
        expectation_class="operator_reference_refresh",
        freshness_window=timedelta(days=1),
        health_endpoint_suffixes=("crypto_reference",),
    ),
}

DEFAULT_REQUIRED_CAPTURE_LANES = frozenset(
    {
        "jupiter-prices",
        "jupiter-quotes",
        "helius-transactions",
        "coinbase-products",
        "coinbase-candles",
        "coinbase-market-trades",
        "coinbase-book",
        "fred-observations",
    }
)


def build_feature_lane_snapshot(
    *,
    required_lanes: tuple[str, ...],
    optional_lanes: tuple[str, ...] = (),
    settings: Settings | None = None,
) -> dict[str, object]:
    """Build the serialized freshness receipt consumed by features."""

    lane_names = tuple(dict.fromkeys(required_lanes + optional_lanes))
    lane_states, blocking_lanes = _resolve_lane_states(
        lane_names=lane_names,
        required_lanes=set(required_lanes),
        settings=settings,
    )
    return {
        "generated_at_utc": _isoformat(utcnow()),
        "required_lanes": lane_states,
        "authorized": not blocking_lanes,
        "blocking_lanes": blocking_lanes,
    }


def build_capture_lane_status_snapshot(
    *, settings: Settings | None = None
) -> dict[str, object]:
    """Build the operator-facing status snapshot for every active capture lane."""

    lane_names = tuple(CAPTURE_LANE_RULES)
    lane_states, blocking_lanes = _resolve_lane_states(
        lane_names=lane_names,
        required_lanes=set(DEFAULT_REQUIRED_CAPTURE_LANES),
        settings=settings,
    )
    return {
        "generated_at_utc": _isoformat(utcnow()),
        "lanes": lane_states,
        "blocking_lanes": blocking_lanes,
    }


def _resolve_lane_states(
    *,
    lane_names: tuple[str, ...],
    required_lanes: set[str],
    settings: Settings | None = None,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    resolved_settings = settings or get_settings()
    provider_capture_pairs = {
        (CAPTURE_LANE_RULES[lane_name].provider, CAPTURE_LANE_RULES[lane_name].capture_type)
        for lane_name in lane_names
    }
    providers = sorted({provider for provider, _ in provider_capture_pairs})
    capture_types = sorted({capture_type for _, capture_type in provider_capture_pairs})

    latest_success_by_lane: dict[str, IngestRun] = {}
    latest_failure_by_lane: dict[str, IngestRun] = {}
    latest_health_by_lane: dict[str, SourceHealthEvent] = {}
    latest_raw_receipt_at_by_lane: dict[str, datetime] = {}

    session = get_session(resolved_settings)
    try:
        for run in (
            session.query(IngestRun)
            .filter(IngestRun.provider.in_(providers))
            .filter(IngestRun.capture_type.in_(capture_types))
            .order_by(IngestRun.finished_at.desc(), IngestRun.started_at.desc())
            .all()
        ):
            lane_name = _lane_name_for_run(run.provider, run.capture_type)
            if lane_name not in lane_names:
                continue
            if run.status == "success" and lane_name not in latest_success_by_lane:
                latest_success_by_lane[lane_name] = run
            elif run.status != "success" and lane_name not in latest_failure_by_lane:
                latest_failure_by_lane[lane_name] = run

        for event in (
            session.query(SourceHealthEvent)
            .filter(SourceHealthEvent.provider.in_(providers))
            .order_by(SourceHealthEvent.checked_at.desc())
            .all()
        ):
            lane_name = _lane_name_for_health_event(event.provider, event.endpoint)
            if lane_name is None or lane_name not in lane_names:
                continue
            if lane_name not in latest_health_by_lane:
                latest_health_by_lane[lane_name] = event

        if "helius-ws-events" in lane_names:
            latest_ws_receipt_at = (
                session.query(RawHeliusWsEvent.captured_at)
                .order_by(RawHeliusWsEvent.captured_at.desc())
                .limit(1)
                .scalar()
            )
            normalized_latest_ws_receipt_at = ensure_utc(latest_ws_receipt_at)
            if normalized_latest_ws_receipt_at is not None:
                latest_raw_receipt_at_by_lane["helius-ws-events"] = (
                    normalized_latest_ws_receipt_at
                )
    finally:
        session.close()

    now = utcnow()
    lane_states: dict[str, dict[str, object]] = {}
    blocking_lanes: list[str] = []
    for lane_name in lane_names:
        rule = CAPTURE_LANE_RULES[lane_name]
        success = latest_success_by_lane.get(lane_name)
        failure = latest_failure_by_lane.get(lane_name)
        health = latest_health_by_lane.get(lane_name)
        latest_raw_receipt_at = latest_raw_receipt_at_by_lane.get(lane_name)

        success_time = ensure_utc(success.finished_at or success.started_at) if success else None
        baseline_time = latest_raw_receipt_at if rule.uses_raw_receipt_presence else success_time
        raw_receipt_missing = rule.uses_raw_receipt_presence and latest_raw_receipt_at is None
        health_missing = health is None
        health_failed = health is not None and not bool(health.is_healthy)

        if rule.readiness_only:
            freshness_state = "readiness_only"
        elif baseline_time is None:
            freshness_state = "never_started"
        else:
            age = now - baseline_time
            if age > rule.freshness_window:
                freshness_state = "stale"
            elif (
                health_missing
                or health_failed
                or raw_receipt_missing
                or age > (rule.freshness_window * _DEGRADED_RATIO)
            ):
                freshness_state = "degraded"
            else:
                freshness_state = "healthy_recent"

        downstream_eligible = freshness_state == "healthy_recent"
        latest_error_summary = _latest_error_summary(
            freshness_state=freshness_state,
            failure=failure,
            health=health,
            raw_receipt_missing=raw_receipt_missing,
        )
        required_for_authorization = lane_name in required_lanes

        lane_states[lane_name] = {
            "provider": rule.provider,
            "capture_type": rule.capture_type,
            "expectation_class": rule.expectation_class,
            "freshness_window_minutes": int(rule.freshness_window.total_seconds() // 60),
            "required_for_authorization": required_for_authorization,
            "last_success_at_utc": _isoformat(success_time),
            "last_failure_at_utc": _isoformat(
                ensure_utc(failure.finished_at or failure.started_at) if failure else None
            ),
            "latest_health_at_utc": _isoformat(ensure_utc(health.checked_at) if health else None),
            "latest_raw_receipt_at_utc": _isoformat(latest_raw_receipt_at),
            "freshness_state": freshness_state,
            "downstream_eligible": downstream_eligible,
            "latest_error_summary": latest_error_summary,
        }
        if required_for_authorization and not downstream_eligible:
            blocking_lanes.append(f"{lane_name}={freshness_state}")

    return lane_states, blocking_lanes


def _lane_name_for_run(provider: str, capture_type: str) -> str | None:
    for lane_name, rule in CAPTURE_LANE_RULES.items():
        if rule.provider == provider and rule.capture_type == capture_type:
            return lane_name
    return None


def _lane_name_for_health_event(provider: str, endpoint: str | None) -> str | None:
    normalized_endpoint = (endpoint or "").strip().lower()
    if not normalized_endpoint:
        return None
    for lane_name, rule in CAPTURE_LANE_RULES.items():
        if rule.provider != provider:
            continue
        if any(normalized_endpoint.endswith(suffix) for suffix in rule.health_endpoint_suffixes):
            return lane_name
    return None


def _latest_error_summary(
    *,
    freshness_state: str,
    failure: IngestRun | None,
    health: SourceHealthEvent | None,
    raw_receipt_missing: bool,
) -> str | None:
    if failure is not None and failure.error_message:
        return failure.error_message
    if health is not None and health.error_message:
        return health.error_message
    if freshness_state == "never_started":
        return "no successful baseline receipt"
    if raw_receipt_missing:
        return "missing raw receipt presence"
    if freshness_state != "readiness_only" and health is None:
        return "missing lane health receipt"
    return None


def _isoformat(dt: datetime | None) -> str | None:
    normalized = ensure_utc(dt)
    if normalized is None:
        return None
    return normalized.isoformat()
