from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from d5_trading_engine.adapters.coinbase.client import CoinbaseClient
from d5_trading_engine.adapters.fred.client import FredClient
from d5_trading_engine.adapters.helius.client import HeliusClient
from d5_trading_engine.adapters.jupiter.client import JupiterClient
from d5_trading_engine.adapters.massive.client import MassiveClient
from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.config.settings import Settings


@pytest.mark.asyncio
async def test_jupiter_fetch_prices_uses_auth_header(httpx_mock) -> None:
    httpx_mock.add_response(method="GET", json={"SOL": {"usdPrice": 150.0}})

    settings = Settings(_env_file=None, jupiter_api_key="test-jupiter-key")
    client = JupiterClient(settings)
    try:
        data = await client.fetch_prices(["SOL", "USDC"])
    finally:
        await client.close()

    assert data["SOL"]["usdPrice"] == 150.0

    request = httpx_mock.get_requests()[0]
    assert request.headers["x-api-key"] == "test-jupiter-key"
    assert request.url.path == "/price/v3"
    assert request.url.params["ids"] == "SOL,USDC"


@pytest.mark.asyncio
async def test_jupiter_rate_limit_enforces_min_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    monotonic_values = iter([10.0, 10.5, 12.5])

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr("d5_trading_engine.adapters.jupiter.client.asyncio.sleep", _fake_sleep)
    monkeypatch.setattr(
        "d5_trading_engine.adapters.jupiter.client.time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
    )

    client = JupiterClient(
        Settings(_env_file=None, jupiter_min_request_interval_seconds=2.0),
    )
    await client._apply_rate_limit()
    await client._apply_rate_limit()

    assert sleep_calls == [1.5]


@pytest.mark.asyncio
async def test_helius_fetch_all_transactions_uses_before_cursor(httpx_mock) -> None:
    first_batch = [{"signature": f"sig-{index:03d}"} for index in range(100)]
    second_batch = [{"signature": "sig-100"}]
    httpx_mock.add_response(method="GET", json=first_batch)
    httpx_mock.add_response(method="GET", json=second_batch)

    settings = Settings(_env_file=None, helius_api_key="test-helius-key")
    client = HeliusClient(settings)
    try:
        data = await client.fetch_all_transactions("wallet-address", max_pages=2)
    finally:
        await client.close()

    assert len(data) == 101

    first_request, second_request = httpx_mock.get_requests()
    assert first_request.url.path == "/v0/addresses/wallet-address/transactions"
    assert first_request.url.params["api-key"] == "test-helius-key"
    assert "before" not in first_request.url.params
    assert second_request.url.params["before"] == "sig-099"


@pytest.mark.asyncio
async def test_helius_fetch_account_info_uses_rpc_url(httpx_mock) -> None:
    httpx_mock.add_response(method="POST", json={"result": {"value": {"owner": "Tokenkeg..."}}})

    settings = Settings(_env_file=None, helius_api_key="test-helius-key")
    client = HeliusClient(settings)
    try:
        data = await client.fetch_account_info("wallet-address")
    finally:
        await client.close()

    assert data["result"]["value"]["owner"] == "Tokenkeg..."

    request = httpx_mock.get_requests()[0]
    assert request.method == "POST"
    assert str(request.url) == settings.helius_rpc_url


def test_fred_fetch_observations_converts_series(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeFred:
        def __init__(self, api_key: str):
            self.api_key = api_key

        def get_series(self, series_id: str, **_: str):
            assert series_id == "DFF"
            return pd.Series(
                [5.25, None],
                index=[pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-02")],
            )

        def get_series_info(self, series_id: str):
            return pd.Series({"title": f"Series {series_id}"})

        def get_vintage_dates(self, _series_id: str):
            return ["2026-01-01"]

    monkeypatch.setattr("d5_trading_engine.adapters.fred.client.Fred", FakeFred)

    client = FredClient(Settings(_env_file=None, fred_api_key="test-fred-key"))
    observations = client.fetch_observations("DFF", start_date="2026-01-01", end_date="2026-01-02")

    assert observations == [
        {"date": "2026-01-01", "value": 5.25},
        {"date": "2026-01-02", "value": None},
    ]


@pytest.mark.asyncio
async def test_massive_fetch_crypto_reference_fails_closed_on_auth(httpx_mock) -> None:
    httpx_mock.add_response(method="GET", status_code=401, text="unauthorized")

    client = MassiveClient(Settings(_env_file=None, massive_api_key="test-massive-key"))
    with pytest.raises(AdapterError) as exc_info:
        await client.fetch_crypto_reference()

    await client.close()

    assert exc_info.value.provider == "massive"
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_coinbase_list_public_products_uses_market_products_path(httpx_mock) -> None:
    httpx_mock.add_response(method="GET", json={"products": [{"product_id": "SOL-USD"}]})

    client = CoinbaseClient(Settings(_env_file=None))
    try:
        data = await client.list_public_products()
    finally:
        await client.close()

    assert data == [{"product_id": "SOL-USD"}]

    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/api/v3/brokerage/market/products"
