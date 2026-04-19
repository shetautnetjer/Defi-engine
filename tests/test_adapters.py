from __future__ import annotations

import gzip
from types import SimpleNamespace

import pandas as pd
import pytest

from d5_trading_engine.adapters.coinbase.client import CoinbaseClient
from d5_trading_engine.adapters.fred.client import FredClient
from d5_trading_engine.adapters.helius.client import HeliusClient
from d5_trading_engine.adapters.jupiter.client import JupiterClient
from d5_trading_engine.adapters.massive.client import MassiveClient
from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.common.errors import AdapterError
from d5_trading_engine.config.settings import Settings
from d5_trading_engine.normalize.coinbase.normalizer import (
    CoinbaseNormalizer,
    derive_coinbase_product_metadata,
)
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import IngestRun, MarketInstrumentRegistry


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
async def test_massive_fetch_crypto_reference_bundle_filters_bounded_tickers(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        json={
            "results": [
                {"ticker": "X:SOLUSD", "base_currency_symbol": "SOL", "quote_currency_symbol": "USD"},
                {"ticker": "X:BTCUSD", "base_currency_symbol": "BTC", "quote_currency_symbol": "USD"},
            ]
        },
    )
    httpx_mock.add_response(
        method="GET",
        json={
            "ticker": "X:SOLUSD",
            "min": {"t": 1_713_350_400_000, "o": 150.0, "h": 151.0, "l": 149.0, "c": 150.5, "v": 42.0},
        },
    )

    client = MassiveClient(Settings(_env_file=None, massive_api_key="test-massive-key"))
    try:
        payload = await client.fetch_crypto_reference_bundle(["X:SOLUSD"])
    finally:
        await client.close()

    assert [row["ticker"] for row in payload["tickers"]] == ["X:SOLUSD"]
    assert payload["snapshots"][0]["ticker"] == "X:SOLUSD"


def test_massive_parse_minute_aggs_csv_handles_gzip_payload() -> None:
    client = MassiveClient(Settings(_env_file=None, massive_api_key="test-massive-key"))
    compressed = gzip.compress(
        (
            "ticker,window_start,open,high,low,close,volume\n"
            "X:SOLUSD,1713350400000,150.0,151.0,149.0,150.5,42.0\n"
        ).encode("utf-8")
    )

    rows = client.parse_minute_aggs_csv(compressed)

    assert rows == [
        {
            "ticker": "X:SOLUSD",
            "window_start": "1713350400000",
            "open": "150.0",
            "high": "151.0",
            "low": "149.0",
            "close": "150.5",
            "volume": "42.0",
        }
    ]


@pytest.mark.asyncio
async def test_massive_fetch_minute_aggs_rest_uses_v2_aggs_range(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        json={
            "ticker": "X:SOLUSD",
            "results": [{"t": 1713350400000, "o": 150.0, "h": 151.0, "l": 149.0, "c": 150.5, "v": 42.0}],
        },
    )

    client = MassiveClient(Settings(_env_file=None, massive_api_key="test-massive-key"))
    try:
        payloads = await client.fetch_minute_aggs_rest("2026-04-16", tickers=["X:SOLUSD"])
    finally:
        await client.close()

    assert payloads["X:SOLUSD"]["ticker"] == "X:SOLUSD"
    request = httpx_mock.get_requests()[0]
    assert request.url.path == "/v2/aggs/ticker/X:SOLUSD/range/1/minute/2026-04-16/2026-04-16"
    assert request.url.params["limit"] == "50000"
    assert request.url.params["apiKey"] == "test-massive-key"


def test_massive_parse_minute_aggs_rest_payloads_matches_csv_shape() -> None:
    client = MassiveClient(Settings(_env_file=None, massive_api_key="test-massive-key"))

    rows = client.parse_minute_aggs_rest_payloads(
        {
            "X:SOLUSD": {
                "ticker": "X:SOLUSD",
                "results": [
                    {
                        "t": 1713350400000,
                        "o": 150.0,
                        "h": 151.0,
                        "l": 149.0,
                        "c": 150.5,
                        "v": 42.0,
                    }
                ],
            }
        }
    )

    assert rows == [
        {
            "ticker": "X:SOLUSD",
            "window_start": "1713350400000",
            "open": "150.0",
            "high": "151.0",
            "low": "149.0",
            "close": "150.5",
            "volume": "42.0",
        }
    ]


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


@pytest.mark.asyncio
async def test_coinbase_list_public_products_forwards_filter_params(httpx_mock) -> None:
    httpx_mock.add_response(method="GET", json={"products": []})

    client = CoinbaseClient(Settings(_env_file=None))
    try:
        await client.list_public_products(
            product_type="FUTURE",
            contract_expiry_type="PERPETUAL",
            futures_underlying_type="FUTURES_UNDERLYING_TYPE_COMMOD",
            limit=25,
            get_all_products=True,
        )
    finally:
        await client.close()

    request = httpx_mock.get_requests()[0]
    assert request.url.params["product_type"] == "FUTURE"
    assert request.url.params["contract_expiry_type"] == "PERPETUAL"
    assert request.url.params["futures_underlying_type"] == "FUTURES_UNDERLYING_TYPE_COMMOD"
    assert request.url.params["limit"] == "25"
    assert request.url.params["get_all_products"] == "true"


@pytest.mark.asyncio
async def test_capture_massive_minute_aggs_falls_back_to_rest_on_flatfile_404(
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from d5_trading_engine.common.errors import AdapterError
    from d5_trading_engine.storage.truth.engine import get_session
    from d5_trading_engine.storage.truth.engine import run_migrations_to_head
    from d5_trading_engine.storage.truth.models import IngestRun, RawMassiveCryptoEvent

    run_migrations_to_head(settings)

    async def _fake_download(self, date_str: str) -> bytes:
        raise AdapterError("massive", "not included", status_code=404)

    async def _fake_rest(self, date_str: str, *, tickers=None):
        assert date_str == "2026-04-16"
        assert tickers == settings.massive_default_tickers
        return {
            "X:SOLUSD": {
                "ticker": "X:SOLUSD",
                "results": [
                    {
                        "t": 1776297600000,
                        "o": 150.0,
                        "h": 151.0,
                        "l": 149.0,
                        "c": 150.5,
                        "v": 42.0,
                    }
                ],
            },
            "X:BTCUSD": {"ticker": "X:BTCUSD", "results": []},
            "X:ETHUSD": {"ticker": "X:ETHUSD", "results": []},
        }

    monkeypatch.setattr(MassiveClient, "download_minute_aggs", _fake_download)
    monkeypatch.setattr(MassiveClient, "fetch_minute_aggs_rest", _fake_rest)

    runner = CaptureRunner(settings)
    run_id = await runner.capture_massive_minute_aggs("2026-04-16")

    raw_dir = settings.raw_dir / "massive" / "2026-04-16"
    raw_files = list(raw_dir.glob("minute_aggs_2026-04-16_*.jsonl"))
    assert len(raw_files) == 1

    session = get_session(settings)
    try:
        ingest_run = session.query(IngestRun).filter_by(run_id=run_id).one()
        raw_event = session.query(RawMassiveCryptoEvent).filter_by(ingest_run_id=run_id).one()
    finally:
        session.close()

    assert ingest_run.status == "success"
    assert ingest_run.records_captured == 1
    assert raw_event.event_type == "minute_aggs_rest"
    assert '"source_mode":"rest"' in raw_event.payload


def test_coinbase_context_selection_includes_spot_futures_and_perps() -> None:
    runner = CaptureRunner(Settings(_env_file=None))

    selected = runner._select_coinbase_products(
        [
            {
                "product_id": "SOL-USD",
                "product_type": "SPOT",
                "base_currency_id": "SOL",
                "quote_currency_id": "USD",
                "status": "online",
            },
            {
                "product_id": "SOL-PERP-INTX",
                "product_type": "FUTURE",
                "display_name": "SOL PERP",
                "quote_currency_id": "USD",
                "future_product_details": {
                    "contract_expiry_type": "PERPETUAL",
                    "contract_root_unit": "SOL",
                    "futures_asset_type": "FUTURES_ASSET_TYPE_CRYPTO",
                },
            },
            {
                "product_id": "GOL-27MAY26-CDE",
                "product_type": "FUTURE",
                "display_name": "GLD 27 MAY 26",
                "quote_currency_id": "USD",
                "future_product_details": {
                    "contract_expiry_type": "EXPIRING",
                    "contract_root_unit": "CDEGLD",
                    "contract_code": "GOL",
                    "group_description": "Gold Futures",
                    "futures_asset_type": "FUTURES_ASSET_TYPE_METALS",
                },
            },
            {
                "product_id": "NOL-20APR26-CDE",
                "product_type": "FUTURE",
                "display_name": "OIL 20 APR 26",
                "quote_currency_id": "USD",
                "future_product_details": {
                    "contract_expiry_type": "EXPIRING",
                    "contract_root_unit": "CDEOIL",
                    "contract_code": "NOL",
                    "group_description": "nano Crude Oil Futures",
                    "futures_asset_type": "FUTURES_ASSET_TYPE_ENERGY",
                },
            },
            {
                "product_id": "ADA-PERP-INTX",
                "product_type": "FUTURE",
                "display_name": "ADA PERP",
                "quote_currency_id": "USD",
                "future_product_details": {
                    "contract_expiry_type": "PERPETUAL",
                    "contract_root_unit": "ADA",
                    "futures_asset_type": "FUTURES_ASSET_TYPE_CRYPTO",
                },
            },
        ]
    )

    assert [product["product_id"] for product in selected] == [
        "SOL-USD",
        "SOL-PERP-INTX",
        "GOL-27MAY26-CDE",
        "NOL-20APR26-CDE",
    ]


@pytest.mark.asyncio
async def test_coinbase_context_loader_merges_spot_future_and_perp_queries() -> None:
    runner = CaptureRunner(Settings(_env_file=None))

    class _FakeClient:
        async def list_public_products(self, **params):
            if params == {}:
                return [
                    {
                        "product_id": "SOL-USD",
                        "product_type": "SPOT",
                        "base_currency_id": "SOL",
                        "quote_currency_id": "USD",
                        "status": "online",
                    }
                ]
            if params == {"product_type": "FUTURE"}:
                return [
                    {
                        "product_id": "GOL-27MAY26-CDE",
                        "product_type": "FUTURE",
                        "display_name": "GLD 27 MAY 26",
                        "quote_currency_id": "USD",
                        "future_product_details": {
                            "contract_expiry_type": "EXPIRING",
                            "contract_root_unit": "CDEGLD",
                            "contract_code": "GOL",
                            "group_description": "Gold Futures",
                            "futures_asset_type": "FUTURES_ASSET_TYPE_METALS",
                        },
                    }
                ]
            if params == {"product_type": "FUTURE", "contract_expiry_type": "PERPETUAL"}:
                return [
                    {
                        "product_id": "SOL-PERP-INTX",
                        "product_type": "FUTURE",
                        "display_name": "SOL PERP",
                        "quote_currency_id": "USD",
                        "future_product_details": {
                            "contract_expiry_type": "PERPETUAL",
                            "contract_root_unit": "SOL",
                            "futures_asset_type": "FUTURES_ASSET_TYPE_CRYPTO",
                        },
                    }
                ]
            raise AssertionError(f"unexpected params: {params}")

    products = await runner._load_coinbase_context_products(_FakeClient())

    assert [product["product_id"] for product in products] == [
        "SOL-USD",
        "GOL-27MAY26-CDE",
        "SOL-PERP-INTX",
    ]


def test_coinbase_product_metadata_derives_future_context_fields() -> None:
    metadata = derive_coinbase_product_metadata(
        {
            "product_id": "PAXG-PERP-INTX",
            "product_type": "FUTURE",
            "display_name": "PAXG PERP",
            "quote_currency_id": "USD",
            "product_venue": "neptune",
            "future_product_details": {
                "contract_expiry_type": "PERPETUAL",
                "contract_root_unit": "PAXG",
                "futures_asset_type": "FUTURES_ASSET_TYPE_CRYPTO",
                "venue": "intx",
            },
        }
    )

    assert metadata["base_symbol"] == "PAXG"
    assert metadata["quote_symbol"] == "USD"
    assert metadata["product_type"] == "FUTURE"
    assert metadata["product_venue"] == "neptune"
    assert metadata["contract_expiry_type"] == "PERPETUAL"
    assert metadata["futures_asset_type"] == "FUTURES_ASSET_TYPE_CRYPTO"
    assert metadata["contract_root_unit"] == "PAXG"


def test_coinbase_normalize_products_stores_future_metadata(settings) -> None:
    run_migrations_to_head(settings)
    normalizer = CoinbaseNormalizer(settings)
    count = normalizer.normalize_products(
        [
            {
                "product_id": "GOL-27MAY26-CDE",
                "product_type": "FUTURE",
                "display_name": "GLD 27 MAY 26",
                "quote_currency_id": "USD",
                "status": "online",
                "product_venue": "cde",
                "future_product_details": {
                    "contract_expiry_type": "EXPIRING",
                    "contract_root_unit": "CDEGLD",
                    "contract_code": "GOL",
                    "group_description": "Gold Futures",
                    "futures_asset_type": "FUTURES_ASSET_TYPE_METALS",
                    "venue": "cde",
                },
            }
        ]
    )

    assert count == 1

    session = get_session(settings)
    try:
        row = session.query(MarketInstrumentRegistry).filter_by(product_id="GOL-27MAY26-CDE").one()
        assert row.base_symbol == "GOLD"
        assert row.quote_symbol == "USD"
        assert row.product_type == "FUTURE"
        assert row.product_venue == "cde"
        assert row.contract_expiry_type == "EXPIRING"
        assert row.futures_asset_type == "FUTURES_ASSET_TYPE_METALS"
        assert row.contract_root_unit == "CDEGLD"
    finally:
        session.close()


@pytest.mark.asyncio
async def test_coinbase_get_public_candles_chunks_large_history_requests(httpx_mock) -> None:
    httpx_mock.add_response(
        method="GET",
        json={
            "candles": [
                {"start": "1713350400", "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"},
                {"start": "1713350460", "open": "2", "high": "2", "low": "2", "close": "2", "volume": "2"},
            ]
        },
    )
    httpx_mock.add_response(
        method="GET",
        json={
            "candles": [
                {"start": "1713350280", "open": "0", "high": "0", "low": "0", "close": "0", "volume": "0"},
                {"start": "1713350400", "open": "1", "high": "1", "low": "1", "close": "1", "volume": "1"},
            ]
        },
    )

    client = CoinbaseClient(Settings(_env_file=None))
    try:
        candles = await client.get_public_candles("SOL-USD", limit=360)
    finally:
        await client.close()

    assert [candle["start"] for candle in candles] == [
        "1713350280",
        "1713350400",
        "1713350460",
    ]

    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert requests[0].url.path == "/api/v3/brokerage/market/products/SOL-USD/candles"
    assert requests[0].url.params["granularity"] == "ONE_MINUTE"


@pytest.mark.asyncio
async def test_capture_coinbase_book_skips_missing_pricebooks(settings, monkeypatch: pytest.MonkeyPatch) -> None:
    run_migrations_to_head(settings)

    async def _fake_list_products(self, **params):
        if params == {}:
            return []
        if params == {"product_type": "FUTURE"}:
            return [
                {
                    "product_id": "GOL-27MAY26-CDE",
                    "product_type": "FUTURE",
                    "display_name": "GLD 27 MAY 26",
                    "quote_currency_id": "USD",
                    "future_product_details": {
                        "contract_expiry_type": "EXPIRING",
                        "contract_root_unit": "CDEGLD",
                        "contract_code": "GOL",
                        "group_description": "Gold Futures",
                        "futures_asset_type": "FUTURES_ASSET_TYPE_METALS",
                    },
                },
            ]
        if params == {"product_type": "FUTURE", "contract_expiry_type": "PERPETUAL"}:
            return [
                {
                    "product_id": "SOL-PERP-INTX",
                    "product_type": "FUTURE",
                    "display_name": "SOL PERP",
                    "quote_currency_id": "USD",
                    "future_product_details": {
                        "contract_expiry_type": "PERPETUAL",
                        "contract_root_unit": "SOL",
                        "futures_asset_type": "FUTURES_ASSET_TYPE_CRYPTO",
                    },
                },
            ]
        raise AssertionError(f"unexpected params: {params}")

    async def _fake_get_book(self, product_id: str, limit: int = 50):
        if product_id == "GOL-27MAY26-CDE":
            raise AdapterError("coinbase", "no pricebook found", status_code=404)
        return {
            "pricebook": {
                "bids": [{"price": "100.0", "size": "1.0"}],
                "asks": [{"price": "101.0", "size": "1.0"}],
            }
        }

    async def _fake_close(self):
        return None

    monkeypatch.setattr(
        "d5_trading_engine.storage.coinbase_raw.engine.initialize",
        lambda _settings: None,
    )
    monkeypatch.setattr(CoinbaseClient, "list_public_products", _fake_list_products)
    monkeypatch.setattr(CoinbaseClient, "get_public_product_book", _fake_get_book)
    monkeypatch.setattr(CoinbaseClient, "close", _fake_close)
    monkeypatch.setattr(
        CaptureRunner,
        "_write_coinbase_raw_rows",
        lambda self, model_class, rows: len(rows),
    )

    runner = CaptureRunner(settings)
    run_id = await runner.capture_coinbase_book()

    session = get_session(settings)
    try:
        ingest_run = session.query(IngestRun).filter_by(run_id=run_id).one()
        assert ingest_run.status == "success"
        assert ingest_run.records_captured == 1
    finally:
        session.close()
