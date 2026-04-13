"""
D5 Trading Engine — Helius WebSocket Client (Scaffold)

WebSocket endpoint: wss://mainnet.helius-rpc.com/?api-key={key}
Method: transactionSubscribe

This is scaffolding for future real-time capture.
The WebSocket client stores raw payloads to JSONL and the raw_helius_ws_event table.

TODO:
- Implement robust reconnection with exponential backoff
- Add heartbeat/ping to avoid 10-minute inactivity timeout
- Add subscription management for multiple addresses
- Rate limit handling
"""

from __future__ import annotations

import asyncio
import json

import websockets

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger

log = get_logger(__name__, provider="helius_ws")


class HeliusWSClient:
    """Helius WebSocket client for real-time transaction subscriptions.

    Currently scaffolded — not fully production-ready.
    Stores raw payloads before normalization.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.ws_url = self.settings.helius_wss_url
        self._ws = None
        self._running = False

    async def subscribe_transactions(
        self,
        addresses: list[str],
        callback=None,
        max_messages: int | None = None,
    ) -> list[dict]:
        """Subscribe to enhanced transactions for given addresses.

        Args:
            addresses: List of Solana addresses to watch (max 50,000).
            callback: Optional async callback(message_dict) for each message.
            max_messages: Optional limit on messages to collect before stopping.

        Returns:
            List of collected message dicts (if max_messages is set).
        """
        collected: list[dict] = []

        subscription_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "transactionSubscribe",
            "params": [
                {"accountInclude": addresses},
                {
                    "commitment": "confirmed",
                    "transactionDetails": "full",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        }

        log.info("ws_connecting", url=self.ws_url[:30] + "...", addresses=len(addresses))

        try:
            async with websockets.connect(self.ws_url) as ws:
                self._ws = ws
                self._running = True

                await ws.send(json.dumps(subscription_request))
                log.info("ws_subscribed", addresses=len(addresses))

                msg_count = 0
                async for message in ws:
                    if not self._running:
                        break

                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        log.warning("ws_invalid_json", message=message[:200])
                        continue

                    collected.append(data)
                    msg_count += 1

                    if callback:
                        await callback(data)

                    log.debug("ws_message", msg_count=msg_count)

                    if max_messages and msg_count >= max_messages:
                        log.info("ws_max_messages_reached", count=msg_count)
                        break

        except websockets.ConnectionClosed as e:
            log.warning("ws_connection_closed", code=e.code, reason=e.reason)
        except Exception as e:
            log.error("ws_error", error=str(e))

        return collected

    async def stop(self) -> None:
        """Signal the WebSocket client to stop."""
        self._running = False
        if self._ws:
            await self._ws.close()
