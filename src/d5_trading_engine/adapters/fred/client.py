"""
D5 Trading Engine — FRED Adapter Client

Wraps the fredapi library for:
- Series metadata (info, search)
- Observation values with realtime/vintage fields
- Vintage date retrieval

API key via FRED_API_KEY env var.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
from fredapi import Fred

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.errors import AdapterError

log = get_logger(__name__, provider="fred")


class FredClient:
    """FRED (Federal Reserve Economic Data) API client.

    Wraps fredapi.Fred for series metadata and observations.
    Preserves realtime/vintage fields for reproducibility.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        if not self.settings.fred_api_key:
            raise AdapterError("fred", "FRED_API_KEY not set")
        self._fred = Fred(api_key=self.settings.fred_api_key)

    def fetch_series_info(self, series_id: str) -> dict:
        """Fetch metadata for a FRED series.

        Args:
            series_id: FRED series identifier (e.g. "DFF", "T10Y2Y").

        Returns:
            Dict with series metadata (title, frequency, units, etc.).
        """
        log.info("fetch_series_info", series_id=series_id)
        try:
            info = self._fred.get_series_info(series_id)
            # Convert pandas Series to dict
            result = info.to_dict() if hasattr(info, "to_dict") else dict(info)
            log.info("fetch_series_info_complete", series_id=series_id, title=result.get("title", ""))
            return result
        except Exception as e:
            raise AdapterError("fred", f"Failed to fetch series info for {series_id}: {e}") from e

    def fetch_observations(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        """Fetch observation values for a FRED series.

        Args:
            series_id: FRED series identifier.
            start_date: Start date (YYYY-MM-DD). Defaults to 1 year ago.
            end_date: End date (YYYY-MM-DD). Defaults to today.

        Returns:
            List of observation dicts with date, value fields.
        """
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        log.info("fetch_observations", series_id=series_id, start=start_date, end=end_date)
        try:
            data = self._fred.get_series(
                series_id,
                observation_start=start_date,
                observation_end=end_date,
            )
            # Convert pandas Series to list of dicts
            observations = []
            if isinstance(data, pd.Series):
                for date, value in data.items():
                    obs = {
                        "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date),
                        "value": float(value) if pd.notna(value) else None,
                    }
                    observations.append(obs)

            log.info("fetch_observations_complete", series_id=series_id, count=len(observations))
            return observations
        except Exception as e:
            raise AdapterError("fred", f"Failed to fetch observations for {series_id}: {e}") from e

    def fetch_observations_with_realtime(
        self,
        series_id: str,
        realtime_start: str | None = None,
        realtime_end: str | None = None,
    ) -> list[dict]:
        """Fetch observations with realtime/vintage period fields.

        Args:
            series_id: FRED series identifier.
            realtime_start: Realtime period start (YYYY-MM-DD).
            realtime_end: Realtime period end (YYYY-MM-DD).

        Returns:
            List of observation dicts with date, value, realtime_start, realtime_end.
        """
        log.info("fetch_observations_realtime", series_id=series_id)
        try:
            kwargs = {}
            if realtime_start:
                kwargs["realtime_start"] = realtime_start
            if realtime_end:
                kwargs["realtime_end"] = realtime_end

            data = self._fred.get_series(series_id, **kwargs)
            observations = []
            if isinstance(data, pd.Series):
                for date, value in data.items():
                    obs = {
                        "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date),
                        "value": float(value) if pd.notna(value) else None,
                        "realtime_start": realtime_start,
                        "realtime_end": realtime_end,
                    }
                    observations.append(obs)

            log.info("fetch_observations_realtime_complete", series_id=series_id, count=len(observations))
            return observations
        except Exception as e:
            raise AdapterError("fred", f"Failed to fetch realtime observations for {series_id}: {e}") from e

    def fetch_vintage_dates(self, series_id: str) -> list[str]:
        """Fetch available vintage dates for a series.

        Args:
            series_id: FRED series identifier.

        Returns:
            List of vintage date strings.
        """
        log.info("fetch_vintage_dates", series_id=series_id)
        try:
            dates = self._fred.get_vintage_dates(series_id)
            result = [str(d) for d in dates] if dates is not None else []
            log.info("fetch_vintage_dates_complete", series_id=series_id, count=len(result))
            return result
        except Exception as e:
            raise AdapterError("fred", f"Failed to fetch vintage dates for {series_id}: {e}") from e
