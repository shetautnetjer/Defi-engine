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
from collections.abc import Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed

from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings, get_settings

log = get_logger(__name__, provider="helius_ws")


def _connection_close_details(exc: ConnectionClosed) -> tuple[int | None, str]:
    """Return stable close metadata across websockets versions."""
    rcvd = getattr(exc, "rcvd", None)
    code = getattr(rcvd, "code", None)
    reason = getattr(rcvd, "reason", None) or "unknown"
    return code, reason


def is_helius_ws_ack(message: dict) -> bool:
    """Return True when a frame is the initial subscription acknowledgement."""
    return "error" not in message and "result" in message and "method" not in message


def is_helius_ws_notification(message: dict) -> bool:
    """Return True when a frame is a transaction notification."""
    return bool(message.get("method") and isinstance(message.get("params"), dict))


def classify_helius_ws_message(message: dict) -> str:
    """Classify the raw Helius websocket frame for storage and receipts."""
    if "error" in message:
        return "subscription_error"
    if is_helius_ws_ack(message):
        return "subscription_ack"
    return message.get("method") or "unknown"


def extract_helius_ws_subscription_id(message: dict) -> str:
    """Extract the most useful subscription identifier from a websocket frame."""
    if is_helius_ws_ack(message):
        return str(message.get("result") or "")
    if is_helius_ws_notification(message):
        return str(message.get("params", {}).get("subscription") or "")
    return str(message.get("id") or "")


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
        self.ack_timeout_seconds = 15.0
        self.receive_timeout_seconds = 30.0
        self.ping_interval_seconds = 20.0
        self.reconnect_backoff_seconds = (1.0, 2.0, 4.0)

    def _build_subscription_request(self, addresses: list[str]) -> dict:
        return {
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

    async def _recv_json(self, ws, timeout_seconds: float, expectation: str) -> dict:
        try:
            payload = await asyncio.wait_for(ws.recv(), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise AdapterError(
                "helius",
                f"WebSocket {expectation} timed out after {timeout_seconds:.0f}s",
            ) from exc
        except ConnectionClosed as exc:
            code, reason = _connection_close_details(exc)
            raise AdapterError(
                "helius",
                f"WebSocket closed while waiting for {expectation}: code={code} reason={reason}",
            ) from exc

        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise AdapterError(
                "helius",
                f"WebSocket returned invalid JSON for {expectation}",
            ) from exc

    async def _record_message(
        self,
        collected: list[dict],
        callback: Callable[[dict], Awaitable[None]] | None,
        message: dict,
    ) -> None:
        collected.append(message)
        if callback:
            await callback(message)

    async def _consume_connection(
        self,
        addresses: list[str],
        callback: Callable[[dict], Awaitable[None]] | None,
        collected: list[dict],
        notification_count: int,
        max_messages: int | None,
    ) -> int:
        subscription_request = self._build_subscription_request(addresses)

        async with websockets.connect(
            self.ws_url,
            ping_interval=self.ping_interval_seconds,
            ping_timeout=self.ack_timeout_seconds,
        ) as ws:
            self._ws = ws
            await ws.send(json.dumps(subscription_request))

            ack = await self._recv_json(
                ws,
                self.ack_timeout_seconds,
                "subscription acknowledgement",
            )
            if "error" in ack:
                raise AdapterError("helius", f"Subscription failed: {ack['error']}")
            if not is_helius_ws_ack(ack):
                raise AdapterError(
                    "helius",
                    "Expected subscription acknowledgement frame from Helius",
                )

            await self._record_message(collected, callback, ack)

            while self._running:
                if max_messages is not None and notification_count >= max_messages:
                    return notification_count

                message = await self._recv_json(
                    ws,
                    self.receive_timeout_seconds,
                    (
                        f"notification message before reaching {max_messages}"
                        if max_messages is not None
                        else "notification message"
                    ),
                )
                if "error" in message:
                    raise AdapterError("helius", f"Subscription failed: {message['error']}")

                await self._record_message(collected, callback, message)
                if is_helius_ws_notification(message):
                    notification_count += 1
                    log.debug("ws_notification", notification_count=notification_count)

            return notification_count

    async def subscribe_transactions(
        self,
        addresses: list[str],
        callback: Callable[[dict], Awaitable[None]] | None = None,
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
        notification_count = 0
        self._running = True
        log.info("ws_connecting", url=self.ws_url[:30] + "...", addresses=len(addresses))

        reconnect_budget = len(self.reconnect_backoff_seconds)
        try:
            for attempt in range(reconnect_budget + 1):
                try:
                    notification_count = await self._consume_connection(
                        addresses,
                        callback,
                        collected,
                        notification_count,
                        max_messages,
                    )
                    if (
                        max_messages is None
                        or notification_count >= max_messages
                        or not self._running
                    ):
                        if max_messages is not None:
                            log.info("ws_max_messages_reached", count=notification_count)
                        return collected
                except AdapterError as exc:
                    if "Subscription failed:" in str(exc):
                        raise
                    if attempt >= reconnect_budget or not self._running:
                        raise
                    delay = self.reconnect_backoff_seconds[attempt]
                    log.warning(
                        "ws_reconnecting",
                        attempt=attempt + 1,
                        delay_seconds=delay,
                        notifications_captured=notification_count,
                        error=str(exc),
                    )
                    await asyncio.sleep(delay)
                finally:
                    self._ws = None
        finally:
            self._running = False

        return collected

    async def stop(self) -> None:
        """Signal the WebSocket client to stop."""
        self._running = False
        if self._ws:
            await self._ws.close()
