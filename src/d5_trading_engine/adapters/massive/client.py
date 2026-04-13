"""
D5 Trading Engine — Massive Adapter Client (Scaffold)

Massive provides crypto market data via REST, WebSocket, and flat files.
This adapter scaffolds all three access methods but fails closed with
clear logging if endpoints are not available under the current plan.

TODO:
- Determine exact endpoint URLs and schemas from Massive documentation
- Test REST endpoints against current key entitlements
- Implement WebSocket subscription logic
- Implement S3-compatible flat-file download
- Parser implementations depend on discovered response shapes

Entitlement uncertainty: The exact endpoints available depend on the
user's Massive subscription plan. This adapter does not guess — it
probes and logs failures clearly.
"""

from __future__ import annotations

from typing import Any

import httpx
import orjson

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.errors import AdapterError

log = get_logger(__name__, provider="massive")

# TODO: Confirm base URL from Massive documentation
_MASSIVE_REST_BASE = "https://api.massive.com"


class MassiveClient:
    """Massive crypto data adapter.

    Scaffolds REST, WebSocket, and flat-file access.
    Fails closed with clear structured logging on auth or entitlement errors.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
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
                base_url=_MASSIVE_REST_BASE,
                headers=self._headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # -------------------------------------------------------------------------
    # REST API
    # -------------------------------------------------------------------------

    async def fetch_crypto_reference(self) -> list[dict]:
        """Fetch crypto reference/metadata from Massive REST API.

        Returns:
            List of crypto asset dicts, or empty list on failure.

        Raises:
            AdapterError: On auth or unexpected errors (fail closed).
        """
        # TODO: Confirm exact endpoint path from Massive docs
        path = "/v1/crypto/reference"
        client = await self._get_client()

        log.info("fetch_crypto_reference", endpoint=path)

        try:
            resp = await client.get(path)
            if resp.status_code in (401, 403):
                log.error(
                    "massive_auth_failed",
                    status_code=resp.status_code,
                    detail="API key may not be valid or plan may not include this endpoint. "
                           "Check Massive dashboard for entitlements.",
                )
                raise AdapterError(
                    "massive",
                    "Authentication failed — check API key and plan entitlements",
                    status_code=resp.status_code,
                )
            resp.raise_for_status()
            return orjson.loads(resp.content)

        except httpx.HTTPStatusError as e:
            log.error(
                "massive_http_error",
                status_code=e.response.status_code,
                detail=e.response.text[:500],
            )
            raise AdapterError(
                "massive",
                f"HTTP error: {e.response.text[:200]}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            log.error("massive_request_error", error=str(e))
            raise AdapterError("massive", f"Request failed: {e}") from e

    # -------------------------------------------------------------------------
    # WebSocket API (scaffold)
    # -------------------------------------------------------------------------

    async def subscribe_crypto_stream(self) -> None:
        """Scaffold for Massive WebSocket crypto stream.

        Not implemented — depends on Massive WebSocket endpoint discovery
        and subscription protocol.

        TODO:
        - Discover WebSocket URL from Massive docs
        - Implement subscription message format
        - Add reconnection logic
        - Store raw payloads to JSONL + raw_massive_crypto_event
        """
        log.warning(
            "massive_ws_not_implemented",
            detail="WebSocket subscription is scaffolded but not yet implemented. "
                   "Need to discover endpoint URL and protocol from Massive docs.",
        )

    # -------------------------------------------------------------------------
    # Flat Files (scaffold)
    # -------------------------------------------------------------------------

    async def list_flat_files(self, date: str | None = None) -> list[str]:
        """Scaffold for listing available Massive flat files via S3.

        Args:
            date: Optional date filter (YYYY-MM-DD).

        Returns:
            List of available file keys.

        TODO:
        - Implement S3-compatible listing using MASSIVE_FLATFILES_KEY
        - Flat files require separate S3 credentials from the REST API key
        - Data available by ~11:00 AM ET next day
        """
        log.warning(
            "massive_flatfiles_not_implemented",
            detail="Flat file access is scaffolded but not yet implemented. "
                   "Requires S3-compatible endpoint and MASSIVE_FLATFILES_KEY.",
        )
        return []
