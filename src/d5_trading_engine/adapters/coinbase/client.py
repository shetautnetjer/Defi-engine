"""Coinbase Advanced Trade public market-data client."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import orjson

from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings

log = get_logger(__name__, provider="coinbase")

_GRANULARITY_SECONDS = {
    "ONE_MINUTE": 60,
    "FIVE_MINUTE": 300,
    "FIFTEEN_MINUTE": 900,
    "THIRTY_MINUTE": 1800,
    "ONE_HOUR": 3600,
    "TWO_HOUR": 7200,
    "SIX_HOUR": 21600,
    "ONE_DAY": 86400,
}


class CoinbaseClient:
    """Coinbase Advanced Trade public market-data client."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.coinbase_api_base
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={"Cache-Control": "no-cache"},
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(self, path: str, **kwargs) -> dict[str, Any]:
        client = await self._get_client()
        try:
            resp = await client.get(path, **kwargs)
            resp.raise_for_status()
            data = orjson.loads(resp.content)
            return data if isinstance(data, dict) else {}
        except httpx.HTTPStatusError as e:
            raise AdapterError(
                "coinbase",
                f"HTTP error on {path}: {e.response.text[:500]}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise AdapterError("coinbase", f"Request failed for {path}: {e}") from e

    async def list_public_products(self) -> list[dict[str, Any]]:
        """List public Advanced Trade products."""
        log.info("coinbase_list_public_products")
        data = await self._request("/market/products")
        products = data.get("products", [])
        log.info("coinbase_list_public_products_complete", count=len(products))
        return products if isinstance(products, list) else []

    async def get_public_candles(
        self,
        product_id: str,
        granularity: str = "ONE_MINUTE",
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        """Fetch public candles for a product."""
        granularity_seconds = _GRANULARITY_SECONDS[granularity]
        end = datetime.now(tz=UTC)
        start = end - timedelta(seconds=granularity_seconds * limit)
        log.info("coinbase_get_public_candles", product_id=product_id, granularity=granularity)
        data = await self._request(
            f"/market/products/{product_id}/candles",
            params={
                "start": int(start.timestamp()),
                "end": int(end.timestamp()),
                "granularity": granularity,
            },
        )
        candles = data.get("candles", [])
        return candles if isinstance(candles, list) else []

    async def get_public_market_trades(
        self,
        product_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch recent public market trades for a product."""
        log.info("coinbase_get_public_market_trades", product_id=product_id, limit=limit)
        data = await self._request(
            f"/market/products/{product_id}/ticker",
            params={"limit": limit},
        )
        trades = data.get("trades", [])
        return trades if isinstance(trades, list) else []

    async def get_public_product_book(
        self,
        product_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Fetch a public L2 book snapshot for a product."""
        log.info("coinbase_get_public_product_book", product_id=product_id, limit=limit)
        return await self._request(
            "/market/product_book",
            params={"product_id": product_id, "limit": limit},
        )
