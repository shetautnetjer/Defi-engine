"""Massive crypto market-data adapter."""

from __future__ import annotations

import asyncio
import csv
import gzip
import io
import time
from typing import ClassVar
from datetime import datetime
from urllib.parse import quote

import httpx
import orjson

from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings

log = get_logger(__name__, provider="massive")


class MassiveClient:
    """Massive REST and flat-file client for bounded crypto market data."""

    _last_rest_minute_aggs_request_monotonic: ClassVar[float | None] = None

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.massive_api_base
        self._client: httpx.AsyncClient | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.massive_api_key}",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs):
        client = await self._get_client()
        try:
            response = await client.request(method, path, **kwargs)
            if response.status_code in (401, 403):
                raise AdapterError(
                    "massive",
                    "Authentication failed — check API key and plan entitlements",
                    status_code=response.status_code,
                )
            response.raise_for_status()
            return orjson.loads(response.content)
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "massive",
                f"HTTP error on {path}: {exc.response.text[:500]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterError("massive", f"Request failed for {path}: {exc}") from exc

    async def fetch_crypto_reference(self, tickers: list[str] | None = None) -> list[dict]:
        """Fetch Massive crypto ticker reference rows."""
        payload = await self._request(
            "GET",
            "/v3/reference/tickers",
            params={"asset_class": "crypto", "limit": 1000},
        )
        results = payload.get("results", payload if isinstance(payload, list) else [])
        if not isinstance(results, list):
            return []
        if not tickers:
            return results
        ticker_set = {ticker.upper() for ticker in tickers}
        return [
            row
            for row in results
            if isinstance(row, dict) and str(row.get("ticker", "")).upper() in ticker_set
        ]

    async def fetch_crypto_snapshot(self, ticker: str) -> dict:
        """Fetch a single crypto snapshot for a bounded ticker."""
        safe_ticker = quote(ticker, safe="")
        return await self._request(
            "GET",
            f"/v2/snapshot/locale/global/markets/crypto/tickers/{safe_ticker}",
        )

    async def fetch_crypto_reference_bundle(self, tickers: list[str] | None = None) -> dict[str, list[dict]]:
        """Fetch bounded reference rows plus per-ticker snapshots."""
        bounded_tickers = tickers or list(self.settings.massive_default_tickers)
        reference_rows = await self.fetch_crypto_reference(bounded_tickers)
        snapshots: list[dict] = []
        for ticker in bounded_tickers:
            snapshot = await self.fetch_crypto_snapshot(ticker)
            if isinstance(snapshot, dict):
                snapshots.append(snapshot)
        return {"tickers": reference_rows, "snapshots": snapshots}

    def build_minute_aggs_url(self, date_str: str) -> str:
        """Build the current bounded flat-file URL for Massive minute aggregates."""
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return (
            f"{self.settings.massive_flatfiles_base}/global_crypto/minute_aggs_v1/"
            f"{parsed:%Y/%m}/{date_str}/{date_str}.csv.gz"
        )

    def build_minute_aggs_s3_key(self, date_str: str) -> str:
        """Build the S3 object key for the requested UTC crypto minute aggregate date."""
        parsed = datetime.strptime(date_str, "%Y-%m-%d")
        return f"global_crypto/minute_aggs_v1/{parsed:%Y/%m}/{date_str}/{date_str}.csv.gz"

    def _build_flatfiles_s3_client(self):
        """Build a Massive S3-compatible client for flat-file access."""
        try:
            import boto3
        except ModuleNotFoundError as exc:
            raise AdapterError(
                "massive",
                "boto3 is required for Massive flat-file S3 access",
            ) from exc

        return boto3.client(
            "s3",
            endpoint_url=self.settings.massive_flatfiles_base,
            aws_access_key_id=self.settings.massive_flatfiles_key,
            aws_secret_access_key=self.settings.massive_flatfiles_secret,
        )

    def build_minute_aggs_rest_url(self, ticker: str, date_str: str) -> str:
        """Build the bounded REST aggregates URL for one ticker and UTC date."""
        safe_ticker = quote(ticker, safe="")
        return (
            f"{self.settings.massive_api_base}/v2/aggs/ticker/{safe_ticker}/range/1/minute/"
            f"{date_str}/{date_str}"
        )

    async def download_minute_aggs(self, date_str: str) -> bytes:
        """Download the gzip minute-aggregate flat file for the requested UTC date."""
        if self.settings.massive_flatfiles_key and self.settings.massive_flatfiles_secret:
            bucket = self.settings.massive_flatfiles_bucket
            key = self.build_minute_aggs_s3_key(date_str)

            def _download_from_s3() -> bytes:
                client = self._build_flatfiles_s3_client()
                try:
                    response = client.get_object(Bucket=bucket, Key=key)
                except Exception as exc:  # pragma: no cover - exercised through botocore at runtime
                    response_meta = getattr(exc, "response", {}) or {}
                    status_code = (response_meta.get("ResponseMetadata") or {}).get("HTTPStatusCode")
                    if status_code in (401, 403):
                        raise AdapterError(
                            "massive",
                            "Authentication failed — check Massive flat-file S3 credentials and entitlements",
                            status_code=status_code,
                        ) from exc
                    if status_code == 404:
                        raise AdapterError(
                            "massive",
                            "Flat-file day not found on Massive S3 surface",
                            status_code=status_code,
                        ) from exc
                    raise AdapterError(
                        "massive",
                        f"Massive flat-file S3 download failed: {exc}",
                        status_code=status_code,
                    ) from exc
                body = response["Body"].read()
                return body

            return await asyncio.to_thread(_download_from_s3)

        url = self.build_minute_aggs_url(date_str)
        headers = {
            "Authorization": f"Bearer {self.settings.massive_flatfiles_key or self.settings.massive_api_key}",
        }
        async with httpx.AsyncClient(timeout=120.0, headers=headers) as client:
            try:
                response = await client.get(url)
                if response.status_code in (401, 403):
                    raise AdapterError(
                        "massive",
                        "Authentication failed — check Massive flat-file entitlements",
                        status_code=response.status_code,
                    )
                response.raise_for_status()
                return response.content
            except httpx.HTTPStatusError as exc:
                raise AdapterError(
                    "massive",
                    f"HTTP error on minute aggregates: {exc.response.text[:500]}",
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                raise AdapterError(
                    "massive",
                    f"Minute aggregate download failed: {exc}",
                ) from exc

    async def fetch_minute_aggs_rest(
        self,
        date_str: str,
        *,
        tickers: list[str] | None = None,
    ) -> dict[str, dict]:
        """Fetch bounded one-minute aggregate payloads from REST for one UTC date."""
        bounded_tickers = tickers or list(self.settings.massive_default_tickers)
        payloads: dict[str, dict] = {}
        for ticker in bounded_tickers:
            attempts = 0
            while True:
                await self._throttle_rest_minute_aggs_request()
                try:
                    payload = await self._request(
                        "GET",
                        f"/v2/aggs/ticker/{quote(ticker, safe='')}/range/1/minute/{date_str}/{date_str}",
                        params={
                            "adjusted": "true",
                            "sort": "asc",
                            "limit": 50000,
                            "apiKey": self.settings.massive_api_key,
                        },
                    )
                    if isinstance(payload, dict):
                        payloads[ticker] = payload
                    break
                except AdapterError as exc:
                    if exc.status_code != 429:
                        raise
                    attempts += 1
                    if attempts > self.settings.massive_rest_minute_aggs_max_retries:
                        raise
                    await asyncio.sleep(self.settings.massive_rest_minute_aggs_retry_sleep_seconds)
        return payloads

    async def _throttle_rest_minute_aggs_request(self) -> None:
        """Throttle bounded REST minute-aggregate requests across the current process."""
        spacing = max(0.0, float(self.settings.massive_rest_minute_aggs_spacing_seconds))
        last_request_at = MassiveClient._last_rest_minute_aggs_request_monotonic
        now = time.monotonic()
        if last_request_at is not None and spacing > 0.0:
            elapsed = now - last_request_at
            if elapsed < spacing:
                await asyncio.sleep(spacing - elapsed)
        MassiveClient._last_rest_minute_aggs_request_monotonic = time.monotonic()

    def parse_minute_aggs_rest_payloads(self, payloads: dict[str, dict]) -> list[dict[str, str]]:
        """Normalize REST aggregate payloads into the same row shape as CSV minute aggs."""
        rows: list[dict[str, str]] = []
        for ticker, payload in payloads.items():
            results = payload.get("results", []) if isinstance(payload, dict) else []
            if not isinstance(results, list):
                continue
            for row in results:
                if not isinstance(row, dict):
                    continue
                rows.append(
                    {
                        "ticker": str(row.get("ticker") or ticker),
                        "window_start": str(row.get("t", "")),
                        "open": str(row.get("o", "")),
                        "high": str(row.get("h", "")),
                        "low": str(row.get("l", "")),
                        "close": str(row.get("c", "")),
                        "volume": str(row.get("v", "")),
                    }
                )
        return rows

    def parse_minute_aggs_csv(self, content: bytes) -> list[dict[str, str]]:
        """Parse a gzip CSV payload into row dictionaries."""
        try:
            decoded = gzip.decompress(content).decode("utf-8")
        except OSError:
            decoded = content.decode("utf-8")
        reader = csv.DictReader(io.StringIO(decoded))
        return [dict(row) for row in reader]
