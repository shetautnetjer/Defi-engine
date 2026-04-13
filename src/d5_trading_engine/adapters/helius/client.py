"""
D5 Trading Engine — Helius REST Adapter Client

Endpoints:
- Enhanced Transactions: GET /v0/addresses/{address}/transactions
- RPC Account Discovery: POST getAccountInfo
- Base URL: https://api-mainnet.helius-rpc.com
- Auth: ?api-key= query parameter
"""

from __future__ import annotations

from typing import Any

import httpx
import orjson

from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings

log = get_logger(__name__, provider="helius")


class HeliusClient:
    """Helius REST client for enhanced transactions and discovery RPC calls."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.base_url = self.settings.helius_api_base
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def fetch_enhanced_transactions(
        self,
        address: str,
        before: str | None = None,
        tx_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Fetch enhanced transactions for a Solana address."""
        client = await self._get_client()
        path = f"/v0/addresses/{address}/transactions"
        params: dict[str, Any] = {"api-key": self.settings.helius_api_key}

        if before:
            params["before"] = before
        if tx_type:
            params["type"] = tx_type
        params["limit"] = limit

        log.info("fetch_enhanced_transactions", address=address[:8] + "...", before=before)
        try:
            resp = await client.get(path, params=params)
            resp.raise_for_status()
            data = orjson.loads(resp.content)
            count = len(data) if isinstance(data, list) else 0
            log.info(
                "fetch_enhanced_transactions_complete",
                address=address[:8] + "...",
                count=count,
            )
            return data if isinstance(data, list) else []
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "helius",
                f"HTTP error fetching transactions for {address}: {exc.response.text[:500]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterError("helius", f"Request failed for {address}: {exc}") from exc

    async def fetch_all_transactions(
        self,
        address: str,
        max_pages: int = 5,
        tx_type: str | None = None,
    ) -> list[dict]:
        """Fetch multiple pages of transactions for an address."""
        all_txs: list[dict] = []
        cursor: str | None = None

        for _page in range(max_pages):
            batch = await self.fetch_enhanced_transactions(
                address,
                before=cursor,
                tx_type=tx_type,
            )
            if not batch:
                break

            all_txs.extend(batch)
            last_sig = batch[-1].get("signature")
            if not last_sig or len(batch) < 100:
                break
            cursor = last_sig

        log.info("fetch_all_transactions_complete", address=address[:8] + "...", total=len(all_txs))
        return all_txs

    async def fetch_account_info(self, address: str) -> dict[str, Any]:
        """Fetch account metadata for discovery and registry seeding."""
        client = await self._get_client()
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getAccountInfo",
            "params": [
                address,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed",
                },
            ],
        }

        log.info("fetch_account_info", address=address[:8] + "...")
        try:
            resp = await client.post(
                self.settings.helius_rpc_url,
                json=payload,
            )
            resp.raise_for_status()
            data = orjson.loads(resp.content)
            return data if isinstance(data, dict) else {}
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                "helius",
                f"HTTP error fetching account info for {address}: {exc.response.text[:500]}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            raise AdapterError(
                "helius",
                f"Request failed for account info {address}: {exc}",
            ) from exc
