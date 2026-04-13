"""
D5 Trading Engine — Time Utilities

All timestamps in the engine are UTC. No local time zones.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Normalize a datetime to a timezone-aware UTC value."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def to_iso(dt: datetime) -> str:
    """Format a datetime as ISO 8601 string with Z suffix."""
    normalized = ensure_utc(dt)
    assert normalized is not None
    return normalized.isoformat().replace("+00:00", "Z")


def from_iso(s: str) -> datetime:
    """Parse an ISO 8601 string into a UTC datetime."""
    normalized = ensure_utc(datetime.fromisoformat(s.replace("Z", "+00:00")))
    assert normalized is not None
    return normalized


def from_unix_timestamp(value: int | float | str | None) -> datetime | None:
    """Parse a Unix timestamp into a timezone-aware UTC datetime."""
    if value in (None, ""):
        return None
    return datetime.fromtimestamp(float(value), tz=UTC)


def derive_event_time_fields(
    source_event_time: datetime | None,
    captured_at: datetime,
    source_time_raw: str | None = None,
) -> dict[str, datetime | str | int | None]:
    """Derive shared UTC helper fields for event-style canonical tables."""
    normalized_source = ensure_utc(source_event_time)
    normalized_captured = ensure_utc(captured_at)
    assert normalized_captured is not None

    primary = normalized_source or normalized_captured
    time_quality = "source" if normalized_source else "captured_fallback"

    return {
        "source_event_time_utc": normalized_source,
        "captured_at_utc": normalized_captured,
        "source_time_raw": source_time_raw,
        "event_date_utc": primary.strftime("%Y-%m-%d"),
        "hour_utc": primary.hour,
        "minute_of_day_utc": (primary.hour * 60) + primary.minute,
        "weekday_utc": primary.weekday(),
        "time_quality": time_quality,
    }


def date_partition() -> str:
    """Return today's date as YYYY-MM-DD partition string."""
    return utcnow().strftime("%Y-%m-%d")
