from __future__ import annotations

import json

import pytest
from websockets.exceptions import ConnectionClosedError
from websockets.frames import Close

from d5_trading_engine.adapters.helius.ws_client import (
    HeliusWSClient,
    classify_helius_ws_message,
    extract_helius_ws_subscription_id,
    is_helius_ws_ack,
    is_helius_ws_notification,
)
from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.config.settings import Settings


class _FakeWebSocket:
    def __init__(self, events: list[dict | Exception]):
        self._events = list(events)
        self.sent_messages: list[dict] = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.closed = True

    async def send(self, payload: str) -> None:
        self.sent_messages.append(json.loads(payload))

    async def recv(self) -> str:
        if not self._events:
            raise AssertionError("Fake websocket ran out of events")

        event = self._events.pop(0)
        if isinstance(event, Exception):
            raise event
        return json.dumps(event)

    async def close(self) -> None:
        self.closed = True


class _FakeConnectFactory:
    def __init__(self, sockets: list[_FakeWebSocket]):
        self._sockets = list(sockets)
        self.calls: list[dict] = []

    def __call__(self, url: str, **kwargs):
        if not self._sockets:
            raise AssertionError("No fake websocket instances remaining")
        ws = self._sockets.pop(0)
        self.calls.append({"url": url, "kwargs": kwargs, "ws": ws})
        return ws


def _notification(subscription_id: int = 7) -> dict:
    return {
        "jsonrpc": "2.0",
        "method": "transactionNotification",
        "params": {
            "subscription": subscription_id,
            "result": {"signature": "sig-001"},
        },
    }


@pytest.mark.asyncio
async def test_helius_ws_ack_does_not_count_toward_message_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ack = {"jsonrpc": "2.0", "result": 7, "id": 1}
    factory = _FakeConnectFactory([_FakeWebSocket([ack, _notification()])])
    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.websockets.connect", factory)

    client = HeliusWSClient(Settings(_env_file=None, helius_api_key="test-helius-key"))
    messages = await client.subscribe_transactions(["wallet-address"], max_messages=1)

    assert len(messages) == 2
    assert is_helius_ws_ack(messages[0])
    assert classify_helius_ws_message(messages[0]) == "subscription_ack"
    assert is_helius_ws_notification(messages[1])
    assert extract_helius_ws_subscription_id(messages[0]) == "7"
    assert extract_helius_ws_subscription_id(messages[1]) == "7"

    sent_request = factory.calls[0]["ws"].sent_messages[0]
    assert sent_request["method"] == "transactionSubscribe"
    assert sent_request["params"][0]["accountInclude"] == ["wallet-address"]
    assert factory.calls[0]["kwargs"]["ping_interval"] == client.ping_interval_seconds
    assert factory.calls[0]["kwargs"]["ping_timeout"] == client.ack_timeout_seconds


@pytest.mark.asyncio
async def test_helius_ws_reconnects_and_continues_collecting_notifications(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reconnect_error = ConnectionClosedError(Close(1011, "boom"), None)
    first_attempt = _FakeWebSocket([{"jsonrpc": "2.0", "result": 7, "id": 1}, reconnect_error])
    second_attempt = _FakeWebSocket(
        [{"jsonrpc": "2.0", "result": 9, "id": 1}, _notification(subscription_id=9)],
    )
    factory = _FakeConnectFactory([first_attempt, second_attempt])
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.websockets.connect", factory)
    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.asyncio.sleep", _fake_sleep)

    client = HeliusWSClient(Settings(_env_file=None, helius_api_key="test-helius-key"))
    messages = await client.subscribe_transactions(["wallet-address"], max_messages=1)

    assert sleep_calls == [1.0]
    assert [classify_helius_ws_message(message) for message in messages] == [
        "subscription_ack",
        "subscription_ack",
        "transactionNotification",
    ]


@pytest.mark.asyncio
async def test_helius_ws_ack_timeout_raises_adapter_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _FakeConnectFactory([_FakeWebSocket([TimeoutError()])])
    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.websockets.connect", factory)

    client = HeliusWSClient(Settings(_env_file=None, helius_api_key="test-helius-key"))
    client.reconnect_backoff_seconds = ()
    with pytest.raises(AdapterError, match="subscription acknowledgement timed out"):
        await client.subscribe_transactions(["wallet-address"], max_messages=1)


@pytest.mark.asyncio
async def test_helius_ws_subscription_error_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _FakeConnectFactory(
        [
            _FakeWebSocket(
                [
                    {
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32600,
                            "message": "transactionSubscribe is not available on the free plan",
                        },
                        "id": 1,
                    },
                ],
            ),
        ],
    )
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.websockets.connect", factory)
    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.asyncio.sleep", _fake_sleep)

    client = HeliusWSClient(Settings(_env_file=None, helius_api_key="test-helius-key"))
    with pytest.raises(AdapterError, match="Subscription failed"):
        await client.subscribe_transactions(["wallet-address"], max_messages=1)

    assert sleep_calls == []


@pytest.mark.asyncio
async def test_helius_ws_reconnect_budget_exhaustion_raises_adapter_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reconnect_error = ConnectionClosedError(Close(1011, "boom"), None)
    factory = _FakeConnectFactory(
        [
            _FakeWebSocket([{"jsonrpc": "2.0", "result": 7, "id": 1}, reconnect_error]),
            _FakeWebSocket([{"jsonrpc": "2.0", "result": 8, "id": 1}, reconnect_error]),
            _FakeWebSocket([{"jsonrpc": "2.0", "result": 9, "id": 1}, reconnect_error]),
            _FakeWebSocket([{"jsonrpc": "2.0", "result": 10, "id": 1}, reconnect_error]),
        ],
    )
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.websockets.connect", factory)
    monkeypatch.setattr("d5_trading_engine.adapters.helius.ws_client.asyncio.sleep", _fake_sleep)

    client = HeliusWSClient(Settings(_env_file=None, helius_api_key="test-helius-key"))
    with pytest.raises(AdapterError, match="before reaching 1"):
        await client.subscribe_transactions(["wallet-address"], max_messages=1)

    assert sleep_calls == [1.0, 2.0, 4.0]
