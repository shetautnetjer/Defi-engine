"""
D5 Trading Engine — Jupiter Adapter Client

Endpoints (Jupiter Developer Platform, 2026):
- Tokens API V2: GET /tokens/v2/tag, /tokens/v2/search
- Price API V3:  GET /price/v3
- Swap API V1:   GET /swap/v1/quote

All endpoints require x-api-key header.
Base URL: https://api.jup.ag
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import orjson

from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings

log = get_logger(__name__, provider="jupiter")


class JupiterClient:
    """Jupiter Developer Platform API client."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.jupiter_api_base
        self._client: httpx.AsyncClient | None = None
        self._last_request_started_at: float | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.settings.jupiter_api_key}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._headers,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _apply_rate_limit(self) -> None:
        """Respect the configured minimum interval between live requests."""
        min_interval = self.settings.jupiter_min_request_interval_seconds
        if min_interval <= 0:
            return

        now_monotonic = time.monotonic()
        if self._last_request_started_at is None:
            self._last_request_started_at = now_monotonic
            return

        elapsed = now_monotonic - self._last_request_started_at
        remaining = min_interval - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
        self._last_request_started_at = time.monotonic()

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make an HTTP request with error handling and throttling."""
        client = await self._get_client()
        await self._apply_rate_limit()
        try:
            resp = await client.request(method, path, **kwargs)
            resp.raise_for_status()
            return orjson.loads(resp.content)
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "jupiter",
                f"HTTP error on {path}: {exc.response.text[:500]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterError("jupiter", f"Request failed for {path}: {exc}") from exc

    async def fetch_token_list(self, tag: str = "verified") -> list[dict]:
        """Fetch token list by tag from Jupiter Tokens API V2."""
        log.info("fetch_token_list", tag=tag)
        data = await self._request("GET", f"/tokens/v2/tag?query={tag}")
        tokens = data if isinstance(data, list) else data.get("tokens", data)
        log.info(
            "fetch_token_list_complete",
            count=len(tokens) if isinstance(tokens, list) else 0,
        )
        return tokens if isinstance(tokens, list) else [tokens]

    async def search_token(self, query: str) -> list[dict]:
        """Search for tokens by symbol, name, or mint."""
        log.info("search_token", query=query)
        data = await self._request("GET", f"/tokens/v2/search?query={query}")
        return data if isinstance(data, list) else [data]

    async def fetch_prices(self, mints: list[str]) -> dict[str, Any]:
        """Fetch USD prices for token mints via Jupiter Price API V3."""
        if not mints:
            return {}

        ids_param = ",".join(mints[:50])
        log.info("fetch_prices", mint_count=len(mints))
        return await self._request("GET", "/price/v3", params={"ids": ids_param})

    async def fetch_quote(
        self,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> dict:
        """Fetch a route-aware swap quote from Jupiter Swap API V1."""
        log.info(
            "fetch_quote",
            input_mint=input_mint[:8] + "...",
            output_mint=output_mint[:8] + "...",
            amount=amount,
        )
        return await self._request(
            "GET",
            "/swap/v1/quote",
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": slippage_bps,
            },
        )
