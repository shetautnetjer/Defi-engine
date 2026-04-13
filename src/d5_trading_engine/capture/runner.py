"""
D5 Trading Engine — Capture Runner

Orchestrates the full capture pipeline per provider:
1. Create ingest_run row
2. Call adapter → get raw data
3. Write raw JSONL to data/raw/{provider}/{date}/
4. Write raw SQL table row (full payload)
5. Call normalizer → write canonical truth tables
6. Log source_health_event
7. Finalize ingest_run (status, records_captured)
"""

from __future__ import annotations

import time
import uuid

import orjson

from d5_trading_engine.common.errors import CaptureError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.raw_store import RawStore
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import IngestRun, SourceHealthEvent

log = get_logger(__name__)


class CaptureRunner:
    """Orchestrates data capture for all providers."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.raw_store = RawStore(self.settings)

    def _start_ingest_run(self, provider: str, capture_type: str) -> str:
        """Create an ingest_run row and return the run_id."""
        run_id = f"{provider}_{capture_type}_{uuid.uuid4().hex[:12]}"
        now = utcnow()
        session = get_session(self.settings)
        try:
            session.add(
                IngestRun(
                    run_id=run_id,
                    provider=provider,
                    capture_type=capture_type,
                    status="running",
                    started_at=now,
                    created_at=now,
                )
            )
            session.commit()
        finally:
            session.close()
        log.info("ingest_run_started", run_id=run_id, provider=provider, capture_type=capture_type)
        return run_id

    def _finish_ingest_run(
        self,
        run_id: str,
        status: str,
        records: int = 0,
        error: str | None = None,
    ) -> None:
        """Update the ingest_run row with final status."""
        session = get_session(self.settings)
        try:
            run = session.query(IngestRun).filter_by(run_id=run_id).first()
            if run:
                run.status = status
                run.finished_at = utcnow()
                run.records_captured = records
                run.error_message = error
                session.commit()
        finally:
            session.close()
        log.info("ingest_run_finished", run_id=run_id, status=status, records=records)

    def _log_health(
        self,
        provider: str,
        endpoint: str,
        is_healthy: bool,
        latency_ms: float,
        status_code: int | None = None,
        error: str | None = None,
    ) -> None:
        """Write a source_health_event row."""
        session = get_session(self.settings)
        try:
            session.add(
                SourceHealthEvent(
                    provider=provider,
                    endpoint=endpoint,
                    status_code=status_code,
                    latency_ms=latency_ms,
                    is_healthy=1 if is_healthy else 0,
                    error_message=error,
                    checked_at=utcnow(),
                )
            )
            session.commit()
        finally:
            session.close()

    def _write_raw_rows(self, model_class, rows: list[dict]) -> int:
        """Write truth-DB raw rows to the database."""
        if not rows:
            return 0
        session = get_session(self.settings)
        try:
            for row_data in rows:
                session.add(model_class(**row_data))
            session.commit()
            return len(rows)
        finally:
            session.close()

    def _write_coinbase_raw_rows(self, model_class, rows: list[dict]) -> int:
        """Write provider-specific Coinbase raw rows to the separate raw store."""
        if not rows:
            return 0

        from d5_trading_engine.storage.coinbase_raw.engine import (
            get_session as get_coinbase_raw_session,
        )

        session = get_coinbase_raw_session(self.settings)
        try:
            for row_data in rows:
                session.add(model_class(**row_data))
            session.commit()
            return len(rows)
        finally:
            session.close()

    def _resolve_tracked_symbols(self) -> set[str]:
        """Resolve stable symbol hints from the pinned mint universe."""
        return {
            self.settings.token_symbol_hints[mint]
            for mint in self.settings.token_universe
            if mint in self.settings.token_symbol_hints
        }

    def _select_coinbase_products(self, products: list[dict]) -> list[dict]:
        """Select Coinbase spot products that intersect the tracked mint universe."""
        tracked_symbols = self._resolve_tracked_symbols()
        selected: list[dict] = []
        for product in products:
            if not isinstance(product, dict):
                continue
            base_symbol = product.get("base_display_symbol") or product.get("base_currency_id")
            quote_symbol = product.get("quote_display_symbol") or product.get("quote_currency_id")
            product_type = (product.get("product_type") or "").upper()
            if base_symbol not in tracked_symbols:
                continue
            if quote_symbol not in {"USD", "USDC"}:
                continue
            if product_type and product_type != "SPOT":
                continue
            selected.append(product)
        return selected

    async def capture_jupiter_tokens(self) -> str:
        """Capture Jupiter token metadata."""
        from d5_trading_engine.adapters.jupiter.client import JupiterClient
        from d5_trading_engine.normalize.jupiter.normalizer import JupiterNormalizer
        from d5_trading_engine.storage.truth.models import RawJupiterTokenResponse

        run_id = self._start_ingest_run("jupiter", "tokens")
        start = time.monotonic()
        try:
            client = JupiterClient(self.settings)
            try:
                tokens = await client.fetch_token_list(tag="verified")
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            captured_at = utcnow()
            self.raw_store.write_jsonl("jupiter", "tokens", tokens, run_id)
            self._write_raw_rows(
                RawJupiterTokenResponse,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "jupiter",
                        "endpoint": "/tokens/v2/tag?query=verified",
                        "payload": orjson.dumps(tokens).decode(),
                        "captured_at": captured_at,
                    }
                ],
            )

            normalizer = JupiterNormalizer(self.settings)
            record_count = normalizer.normalize_tokens(tokens, run_id)
            self._log_health("jupiter", "/tokens/v2", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", record_count)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("jupiter", "/tokens/v2", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Jupiter token capture failed: {exc}") from exc

        return run_id

    async def capture_jupiter_prices(self) -> str:
        """Capture Jupiter prices for the configured token universe."""
        from d5_trading_engine.adapters.jupiter.client import JupiterClient
        from d5_trading_engine.normalize.jupiter.normalizer import JupiterNormalizer
        from d5_trading_engine.storage.truth.models import RawJupiterPriceResponse

        run_id = self._start_ingest_run("jupiter", "prices")
        start = time.monotonic()
        try:
            client = JupiterClient(self.settings)
            try:
                mints = self.settings.token_universe
                data = await client.fetch_prices(mints)
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            captured_at = utcnow()
            self.raw_store.write_single("jupiter", "prices", data, run_id)
            self._write_raw_rows(
                RawJupiterPriceResponse,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "jupiter",
                        "mints_queried": ",".join(mints),
                        "payload": orjson.dumps(data).decode(),
                        "captured_at": captured_at,
                    }
                ],
            )

            normalizer = JupiterNormalizer(self.settings)
            record_count = normalizer.normalize_prices(data, run_id)
            self._log_health("jupiter", "/price/v3", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", record_count)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("jupiter", "/price/v3", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Jupiter price capture failed: {exc}") from exc

        return run_id

    async def capture_jupiter_quotes(self) -> str:
        """Capture two-sided Jupiter spot quotes for the configured universe."""
        from d5_trading_engine.adapters.jupiter.client import JupiterClient
        from d5_trading_engine.normalize.jupiter.normalizer import JupiterNormalizer
        from d5_trading_engine.storage.truth.models import RawJupiterQuoteResponse

        run_id = self._start_ingest_run("jupiter", "quotes")
        start = time.monotonic()
        total_records = 0
        usdc_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

        try:
            client = JupiterClient(self.settings)
            normalizer = JupiterNormalizer(self.settings)

            try:
                for mint in self.settings.token_universe:
                    if mint == usdc_mint:
                        continue

                    for amount in self.settings.quote_amounts_lamports:
                        for request_direction, input_mint, output_mint in (
                            ("token_to_usdc", mint, usdc_mint),
                            ("usdc_to_token", usdc_mint, mint),
                        ):
                            try:
                                requested_at = utcnow()
                                request_start = time.monotonic()
                                quote = await client.fetch_quote(input_mint, output_mint, amount)
                                response_latency_ms = (time.monotonic() - request_start) * 1000
                                captured_at = utcnow()

                                self.raw_store.write_single("jupiter", "quote", quote, run_id)
                                self._write_raw_rows(
                                    RawJupiterQuoteResponse,
                                    [
                                        {
                                            "ingest_run_id": run_id,
                                            "provider": "jupiter",
                                            "input_mint": input_mint,
                                            "output_mint": output_mint,
                                            "amount": str(amount),
                                            "request_direction": request_direction,
                                            "requested_at": requested_at,
                                            "response_latency_ms": response_latency_ms,
                                            "source_event_time_utc": None,
                                            "source_time_raw": None,
                                            "payload": orjson.dumps(quote).decode(),
                                            "captured_at": captured_at,
                                        }
                                    ],
                                )
                                total_records += normalizer.normalize_quote(
                                    quote,
                                    run_id,
                                    request_direction=request_direction,
                                    requested_at=requested_at,
                                    response_latency_ms=response_latency_ms,
                                    captured_at=captured_at,
                                )
                            except Exception as exc:
                                log.warning(
                                    "quote_capture_skipped",
                                    mint=mint[:8],
                                    direction=request_direction,
                                    amount=amount,
                                    error=str(exc),
                                )
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("jupiter", "/swap/v1/quote", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("jupiter", "/swap/v1/quote", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Jupiter quote capture failed: {exc}") from exc

        return run_id

    async def capture_helius_transactions(self, addresses: list[str] | None = None) -> str:
        """Capture Helius enhanced transactions for tracked addresses."""
        from d5_trading_engine.adapters.helius.client import HeliusClient
        from d5_trading_engine.normalize.helius.normalizer import HeliusNormalizer
        from d5_trading_engine.storage.truth.models import RawHeliusEnhancedTransaction

        tracked_addresses = addresses or self.settings.helius_tracked_addresses
        if not tracked_addresses:
            message = "Helius capture requires HELIUS_TRACKED_ADDRESSES or explicit addresses."
            log.error("no_tracked_addresses", detail=message)
            raise CaptureError(message)

        run_id = self._start_ingest_run("helius", "enhanced_transactions")
        start = time.monotonic()
        total_records = 0

        try:
            client = HeliusClient(self.settings)
            normalizer = HeliusNormalizer(self.settings)
            try:
                for address in tracked_addresses:
                    txs = await client.fetch_enhanced_transactions(address)
                    if not txs:
                        continue

                    captured_at = utcnow()
                    self.raw_store.write_jsonl("helius", "enhanced_tx", txs, run_id)
                    self._write_raw_rows(
                        RawHeliusEnhancedTransaction,
                        [
                            {
                                "ingest_run_id": run_id,
                                "provider": "helius",
                                "address": address,
                                "signature": tx.get("signature"),
                                "tx_type": tx.get("type"),
                                "payload": orjson.dumps(tx).decode(),
                                "captured_at": captured_at,
                            }
                            for tx in txs
                        ],
                    )
                    total_records += normalizer.normalize_transactions(txs, run_id)
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "/v0/addresses/*/transactions", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health(
                "helius",
                "/v0/addresses/*/transactions",
                False,
                elapsed_ms,
                error=str(exc),
            )
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Helius transaction capture failed: {exc}") from exc

        return run_id

    async def capture_helius_discovery(self, addresses: list[str] | None = None) -> str:
        """Capture Helius account discovery for tracked addresses."""
        from d5_trading_engine.adapters.helius.client import HeliusClient
        from d5_trading_engine.normalize.helius.normalizer import HeliusNormalizer
        from d5_trading_engine.storage.truth.models import RawHeliusAccountDiscovery

        tracked_addresses = addresses or self.settings.helius_tracked_addresses
        if not tracked_addresses:
            message = "Helius discovery requires HELIUS_TRACKED_ADDRESSES or explicit addresses."
            log.error("no_tracked_addresses", detail=message)
            raise CaptureError(message)

        run_id = self._start_ingest_run("helius", "account_discovery")
        start = time.monotonic()

        try:
            client = HeliusClient(self.settings)
            normalizer = HeliusNormalizer(self.settings)
            discoveries: list[dict] = []
            try:
                for address in tracked_addresses:
                    payload = await client.fetch_account_info(address)
                    if not payload:
                        continue
                    discoveries.append({"address": address, **payload})
            finally:
                await client.close()

            captured_at = utcnow()
            self.raw_store.write_jsonl("helius", "account_discovery", discoveries, run_id)
            self._write_raw_rows(
                RawHeliusAccountDiscovery,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "helius",
                        "address": discovery.get("address"),
                        "owner_program_id": (
                            discovery.get("result", {}).get("value", {}) or {}
                        ).get("owner"),
                        "payload": orjson.dumps(discovery).decode(),
                        "captured_at": captured_at,
                    }
                    for discovery in discoveries
                ],
            )
            total_records = normalizer.normalize_account_discovery(discoveries, run_id)

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "getAccountInfo", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "getAccountInfo", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Helius discovery capture failed: {exc}") from exc

        return run_id

    async def capture_helius_ws_events(self, addresses: list[str] | None = None) -> str:
        """Capture a bounded set of raw Helius websocket transaction notifications."""
        from d5_trading_engine.adapters.helius.ws_client import HeliusWSClient
        from d5_trading_engine.storage.truth.models import RawHeliusWsEvent

        tracked_addresses = addresses or self.settings.helius_tracked_addresses
        if not tracked_addresses:
            message = (
                "Helius websocket capture requires HELIUS_TRACKED_ADDRESSES "
                "or explicit addresses."
            )
            log.error("no_tracked_addresses", detail=message)
            raise CaptureError(message)

        run_id = self._start_ingest_run("helius", "ws_events")
        start = time.monotonic()
        try:
            client = HeliusWSClient(self.settings)
            messages = await client.subscribe_transactions(
                tracked_addresses,
                max_messages=self.settings.helius_ws_max_messages,
            )

            captured_at = utcnow()
            self.raw_store.write_jsonl("helius", "ws_event", messages, run_id)
            self._write_raw_rows(
                RawHeliusWsEvent,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "helius",
                        "subscription_id": str(
                            message.get("params", {}).get("subscription")
                            or message.get("id")
                            or ""
                        ),
                        "event_type": message.get("method") or "transactionNotification",
                        "payload": orjson.dumps(message).decode(),
                        "captured_at": captured_at,
                    }
                    for message in messages
                ],
            )

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "transactionSubscribe", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", len(messages))
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "transactionSubscribe", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Helius websocket capture failed: {exc}") from exc

        return run_id

    async def capture_coinbase_products(self) -> str:
        """Capture tracked Coinbase spot products into raw and canonical stores."""
        from d5_trading_engine.adapters.coinbase.client import CoinbaseClient
        from d5_trading_engine.normalize.coinbase.normalizer import CoinbaseNormalizer
        from d5_trading_engine.storage.coinbase_raw.engine import (
            initialize as initialize_coinbase_raw,
        )
        from d5_trading_engine.storage.coinbase_raw.models import RawCoinbaseProduct

        run_id = self._start_ingest_run("coinbase", "products")
        start = time.monotonic()
        try:
            initialize_coinbase_raw(self.settings)
            client = CoinbaseClient(self.settings)
            try:
                products = await client.list_public_products()
            finally:
                await client.close()

            selected_products = self._select_coinbase_products(products)
            captured_at = utcnow()
            self.raw_store.write_jsonl("coinbase", "products", selected_products, run_id)
            self._write_coinbase_raw_rows(
                RawCoinbaseProduct,
                [
                    {
                        "ingest_run_id": run_id,
                        "product_id": product.get("product_id") or product.get("productId"),
                        "payload": orjson.dumps(product).decode(),
                        "captured_at": captured_at,
                    }
                    for product in selected_products
                ],
            )

            normalizer = CoinbaseNormalizer(self.settings)
            total_records = normalizer.normalize_products(selected_products)
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("coinbase", "/market/products", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("coinbase", "/market/products", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Coinbase product capture failed: {exc}") from exc

        return run_id

    async def capture_coinbase_candles(self) -> str:
        """Capture Coinbase candles for the tracked spot products."""
        from d5_trading_engine.adapters.coinbase.client import CoinbaseClient
        from d5_trading_engine.normalize.coinbase.normalizer import CoinbaseNormalizer
        from d5_trading_engine.storage.coinbase_raw.engine import (
            initialize as initialize_coinbase_raw,
        )
        from d5_trading_engine.storage.coinbase_raw.models import RawCoinbaseCandleResponse

        run_id = self._start_ingest_run("coinbase", "candles")
        start = time.monotonic()
        total_records = 0
        try:
            initialize_coinbase_raw(self.settings)
            client = CoinbaseClient(self.settings)
            normalizer = CoinbaseNormalizer(self.settings)
            try:
                products = self._select_coinbase_products(await client.list_public_products())
                for product in products:
                    product_id = product.get("product_id") or product.get("productId")
                    if not product_id:
                        continue
                    candles = await client.get_public_candles(product_id)
                    if not candles:
                        continue
                    captured_at = utcnow()
                    self.raw_store.write_jsonl("coinbase", f"candles_{product_id}", candles, run_id)
                    self._write_coinbase_raw_rows(
                        RawCoinbaseCandleResponse,
                        [
                            {
                                "ingest_run_id": run_id,
                                "product_id": product_id,
                                "granularity": "ONE_MINUTE",
                                "payload": orjson.dumps(candle).decode(),
                                "captured_at": captured_at,
                            }
                            for candle in candles
                        ],
                    )
                    total_records += normalizer.normalize_candles(product_id, candles, run_id)
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("coinbase", "/market/products/*/candles", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health(
                "coinbase",
                "/market/products/*/candles",
                False,
                elapsed_ms,
                error=str(exc),
            )
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Coinbase candle capture failed: {exc}") from exc

        return run_id

    async def capture_coinbase_market_trades(self) -> str:
        """Capture Coinbase recent trade prints for tracked spot products."""
        from d5_trading_engine.adapters.coinbase.client import CoinbaseClient
        from d5_trading_engine.normalize.coinbase.normalizer import CoinbaseNormalizer
        from d5_trading_engine.storage.coinbase_raw.engine import (
            initialize as initialize_coinbase_raw,
        )
        from d5_trading_engine.storage.coinbase_raw.models import RawCoinbaseTradeResponse

        run_id = self._start_ingest_run("coinbase", "market_trades")
        start = time.monotonic()
        total_records = 0
        try:
            initialize_coinbase_raw(self.settings)
            client = CoinbaseClient(self.settings)
            normalizer = CoinbaseNormalizer(self.settings)
            try:
                products = self._select_coinbase_products(await client.list_public_products())
                for product in products:
                    product_id = product.get("product_id") or product.get("productId")
                    if not product_id:
                        continue
                    trades = await client.get_public_market_trades(product_id)
                    if not trades:
                        continue
                    captured_at = utcnow()
                    self.raw_store.write_jsonl(
                        "coinbase",
                        f"market_trades_{product_id}",
                        trades,
                        run_id,
                    )
                    self._write_coinbase_raw_rows(
                        RawCoinbaseTradeResponse,
                        [
                            {
                                "ingest_run_id": run_id,
                                "product_id": product_id,
                                "payload": orjson.dumps(trade).decode(),
                                "captured_at": captured_at,
                            }
                            for trade in trades
                        ],
                    )
                    total_records += normalizer.normalize_market_trades(
                        product_id,
                        trades,
                        run_id,
                    )
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("coinbase", "/market/products/*/ticker", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health(
                "coinbase",
                "/market/products/*/ticker",
                False,
                elapsed_ms,
                error=str(exc),
            )
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Coinbase market trade capture failed: {exc}") from exc

        return run_id

    async def capture_coinbase_book(self) -> str:
        """Capture Coinbase L2 book snapshots for tracked spot products."""
        from d5_trading_engine.adapters.coinbase.client import CoinbaseClient
        from d5_trading_engine.normalize.coinbase.normalizer import CoinbaseNormalizer
        from d5_trading_engine.storage.coinbase_raw.engine import (
            initialize as initialize_coinbase_raw,
        )
        from d5_trading_engine.storage.coinbase_raw.models import RawCoinbaseBookSnapshot

        run_id = self._start_ingest_run("coinbase", "book")
        start = time.monotonic()
        total_records = 0
        try:
            initialize_coinbase_raw(self.settings)
            client = CoinbaseClient(self.settings)
            normalizer = CoinbaseNormalizer(self.settings)
            try:
                products = self._select_coinbase_products(await client.list_public_products())
                for product in products:
                    product_id = product.get("product_id") or product.get("productId")
                    if not product_id:
                        continue
                    book = await client.get_public_product_book(product_id)
                    if not book:
                        continue
                    captured_at = utcnow()
                    self.raw_store.write_single("coinbase", f"book_{product_id}", book, run_id)
                    self._write_coinbase_raw_rows(
                        RawCoinbaseBookSnapshot,
                        [
                            {
                                "ingest_run_id": run_id,
                                "product_id": product_id,
                                "payload": orjson.dumps(book).decode(),
                                "captured_at": captured_at,
                            }
                        ],
                    )
                    total_records += normalizer.normalize_book_snapshot(product_id, book, run_id)
            finally:
                await client.close()

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("coinbase", "/market/product_book", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("coinbase", "/market/product_book", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Coinbase order book capture failed: {exc}") from exc

        return run_id

    def capture_fred_series(self) -> str:
        """Register default FRED series metadata."""
        from d5_trading_engine.adapters.fred.client import FredClient
        from d5_trading_engine.normalize.fred.normalizer import FredNormalizer
        from d5_trading_engine.storage.truth.models import RawFredSeriesResponse

        run_id = self._start_ingest_run("fred", "series_registry")
        start = time.monotonic()
        total_records = 0

        try:
            client = FredClient(self.settings)
            normalizer = FredNormalizer(self.settings)
            captured_at = utcnow()

            for series_id in self.settings.fred_default_series:
                try:
                    info = client.fetch_series_info(series_id)
                    self.raw_store.write_single("fred", f"series_{series_id}", info, run_id)
                    self._write_raw_rows(
                        RawFredSeriesResponse,
                        [
                            {
                                "ingest_run_id": run_id,
                                "provider": "fred",
                                "series_id": series_id,
                                "payload": orjson.dumps(info).decode(),
                                "captured_at": captured_at,
                            }
                        ],
                    )
                    total_records += normalizer.normalize_series(info, series_id, run_id)
                except Exception as exc:
                    log.warning("fred_series_skipped", series_id=series_id, error=str(exc))

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("fred", "series_info", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("fred", "series_info", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"FRED series capture failed: {exc}") from exc

        return run_id

    def capture_fred_observations(self) -> str:
        """Capture FRED observations for all registered series."""
        from d5_trading_engine.adapters.fred.client import FredClient
        from d5_trading_engine.normalize.fred.normalizer import FredNormalizer
        from d5_trading_engine.storage.truth.models import RawFredObservationResponse

        run_id = self._start_ingest_run("fred", "observations")
        start = time.monotonic()
        total_records = 0

        try:
            client = FredClient(self.settings)
            normalizer = FredNormalizer(self.settings)
            captured_at = utcnow()

            for series_id in self.settings.fred_default_series:
                try:
                    observations = client.fetch_observations(series_id)
                    if not observations:
                        continue
                    self.raw_store.write_jsonl("fred", f"obs_{series_id}", observations, run_id)
                    self._write_raw_rows(
                        RawFredObservationResponse,
                        [
                            {
                                "ingest_run_id": run_id,
                                "provider": "fred",
                                "series_id": series_id,
                                "payload": orjson.dumps(observations).decode(),
                                "captured_at": captured_at,
                            }
                        ],
                    )
                    total_records += normalizer.normalize_observations(
                        observations,
                        series_id,
                        run_id,
                    )
                except Exception as exc:
                    log.warning("fred_obs_skipped", series_id=series_id, error=str(exc))

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("fred", "observations", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", total_records)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("fred", "observations", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"FRED observation capture failed: {exc}") from exc

        return run_id

    async def capture_massive_crypto(self) -> str:
        """Attempt Massive crypto data capture (fail closed)."""
        from d5_trading_engine.adapters.massive.client import MassiveClient
        from d5_trading_engine.storage.truth.models import RawMassiveCryptoEvent

        run_id = self._start_ingest_run("massive", "crypto_reference")
        start = time.monotonic()

        try:
            client = MassiveClient(self.settings)
            try:
                data = await client.fetch_crypto_reference()
            finally:
                await client.close()

            captured_at = utcnow()
            rows = data if isinstance(data, list) else [data]
            self.raw_store.write_jsonl("massive", "crypto_reference", rows, run_id)
            count = self._write_raw_rows(
                RawMassiveCryptoEvent,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "massive",
                        "event_type": "crypto_reference",
                        "payload": orjson.dumps(row).decode(),
                        "captured_at": captured_at,
                    }
                    for row in rows
                ],
            )

            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("massive", "crypto_reference", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", count)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("massive", "crypto_reference", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            log.error("massive_capture_failed_closed", error=str(exc))
            raise CaptureError(f"Massive crypto capture failed closed: {exc}") from exc

        return run_id
