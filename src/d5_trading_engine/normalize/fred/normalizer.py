"""
D5 Trading Engine — FRED Normalizer

Transforms raw FRED API responses into canonical truth tables:
- fred_series_registry (upsert)
- fred_observation (append with realtime fields)
"""

from __future__ import annotations

from datetime import datetime

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import FredSeriesRegistry, FredObservation

log = get_logger(__name__, normalizer="fred")


class FredNormalizer:
    """Normalize FRED series and observation data into canonical truth."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def normalize_series(self, info: dict, series_id: str, ingest_run_id: str) -> int:
        """Upsert a FRED series into fred_series_registry.

        Args:
            info: Raw series info dict from fredapi.
            series_id: FRED series identifier.
            ingest_run_id: Ingest run ID.

        Returns:
            1 if written/updated, 0 otherwise.
        """
        session = get_session(self.settings)
        now = utcnow()

        try:
            existing = session.query(FredSeriesRegistry).filter_by(series_id=series_id).first()
            if existing:
                existing.title = info.get("title", existing.title)
                existing.frequency = info.get("frequency", existing.frequency)
                existing.units = info.get("units", existing.units)
                existing.seasonal_adjustment = info.get("seasonal_adjustment", existing.seasonal_adjustment)
                last_updated = info.get("last_updated")
                if last_updated and isinstance(last_updated, str):
                    try:
                        existing.last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                    except (ValueError, TypeError):
                        pass
                existing.updated_at = now
            else:
                reg = FredSeriesRegistry(
                    series_id=series_id,
                    title=info.get("title"),
                    frequency=info.get("frequency"),
                    units=info.get("units"),
                    seasonal_adjustment=info.get("seasonal_adjustment"),
                    provider="fred",
                    first_seen_at=now,
                    updated_at=now,
                )
                session.add(reg)

            session.commit()
            log.info("normalize_series_complete", series_id=series_id)
            return 1
        finally:
            session.close()

    def normalize_observations(
        self, observations: list[dict], series_id: str, ingest_run_id: str
    ) -> int:
        """Write FRED observations to fred_observation.

        Args:
            observations: List of observation dicts with date, value fields.
            series_id: FRED series identifier.
            ingest_run_id: Ingest run ID.

        Returns:
            Number of observations written.
        """
        session = get_session(self.settings)
        now = utcnow()
        count = 0

        try:
            for obs in observations:
                if not isinstance(obs, dict):
                    continue
                record = FredObservation(
                    ingest_run_id=ingest_run_id,
                    series_id=series_id,
                    observation_date=obs.get("date", ""),
                    value=obs.get("value"),
                    realtime_start=obs.get("realtime_start"),
                    realtime_end=obs.get("realtime_end"),
                    provider="fred",
                    captured_at=now,
                )
                session.add(record)
                count += 1

            session.commit()
            log.info("normalize_observations_complete", series_id=series_id, count=count)
        finally:
            session.close()

        return count
