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
from pathlib import Path

import orjson

from d5_trading_engine.common.errors import AdapterError, CaptureError
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd
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

    def write_capture_receipts(
        self,
        run_id: str,
        *,
        context: dict[str, object] | None = None,
    ) -> Path | None:
        """Write capture summary artifacts plus SQL artifact receipts."""
        session = get_session(self.settings)
        try:
            run = session.query(IngestRun).filter_by(run_id=run_id).first()
            if run is None:
                log.warning("capture_receipts_skipped_missing_run", run_id=run_id)
                return None
            health = (
                session.query(SourceHealthEvent)
                .filter_by(provider=run.provider)
                .order_by(SourceHealthEvent.checked_at.desc())
                .first()
            )
        finally:
            session.close()

        artifact_dir = self.settings.data_dir / "research" / "capture_runs" / run_id
        owner_type = "capture_run"
        owner_key = run_id
        config_payload = {
            "run_id": run.run_id,
            "provider": run.provider,
            "capture_type": run.capture_type,
            "artifact_dir": str(artifact_dir),
            "context": context or {},
        }
        summary_payload = {
            "run_id": run.run_id,
            "provider": run.provider,
            "capture_type": run.capture_type,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "records_captured": run.records_captured,
            "error_message": run.error_message,
            "latest_health": {
                "endpoint": health.endpoint if health else None,
                "is_healthy": bool(health.is_healthy) if health else None,
                "status_code": health.status_code if health else None,
                "latency_ms": health.latency_ms if health else None,
                "checked_at": health.checked_at.isoformat() if health and health.checked_at else None,
                "error_message": health.error_message if health else None,
            },
        }

        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="capture_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "capture_summary.json",
            summary_payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="capture_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "capture_run.qmd",
                title=f"capture_{run.provider}_{run.capture_type}",
                summary_lines=[
                    f"- run id: `{run.run_id}`",
                    f"- provider: `{run.provider}`",
                    f"- capture type: `{run.capture_type}`",
                    f"- status: `{run.status}`",
                    f"- records captured: `{run.records_captured or 0}`",
                ],
                sections=[
                    (
                        "Timing",
                        [
                            f"- started at: `{summary_payload['started_at']}`",
                            f"- finished at: `{summary_payload['finished_at']}`",
                        ],
                    ),
                    (
                        "Latest Health",
                        [
                            f"- endpoint: `{summary_payload['latest_health']['endpoint']}`",
                            f"- healthy: `{summary_payload['latest_health']['is_healthy']}`",
                            f"- status code: `{summary_payload['latest_health']['status_code']}`",
                            f"- latency ms: `{summary_payload['latest_health']['latency_ms']}`",
                        ],
                    ),
                    (
                        "Context",
                        [f"- `{key}`: `{value}`" for key, value in sorted((context or {}).items())]
                        or ["- none"],
                    ),
                ],
            ),
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="capture_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        return artifact_dir

    def _resolve_tracked_symbols(self) -> set[str]:
        """Resolve stable symbol hints from the pinned mint universe."""
        return {
            self.settings.token_symbol_hints[mint].upper()
            for mint in self.settings.token_universe
            if mint in self.settings.token_symbol_hints
        }

    def _resolve_coinbase_context_symbols(self) -> set[str]:
        """Resolve the bounded Coinbase context symbol universe."""
        return self._resolve_tracked_symbols() | {
            symbol.upper() for symbol in self.settings.coinbase_context_symbols
        }

    def _select_coinbase_products(self, products: list[dict]) -> list[dict]:
        """Select bounded Coinbase context products for spot, futures, and perps."""
        from d5_trading_engine.normalize.coinbase.normalizer import derive_coinbase_product_metadata

        tracked_symbols = self._resolve_coinbase_context_symbols()
        selected: list[dict] = []
        for product in products:
            if not isinstance(product, dict):
                continue
            metadata = derive_coinbase_product_metadata(product)
            base_symbol = (metadata["base_symbol"] or "").upper()
            quote_symbol = (metadata["quote_symbol"] or "").upper()
            product_type = (metadata["product_type"] or "").upper()
            if base_symbol not in tracked_symbols:
                continue
            if product_type == "SPOT" and quote_symbol in {"USD", "USDC"}:
                selected.append(product)
                continue
            if product_type == "FUTURE":
                selected.append(product)
        return selected

    async def _load_coinbase_context_products(self, client) -> list[dict]:
        """Load the bounded Coinbase spot + futures/perp context inventory."""
        merged_products: dict[str, dict] = {}
        for params in (
            {},
            {"product_type": "FUTURE"},
            {"product_type": "FUTURE", "contract_expiry_type": "PERPETUAL"},
        ):
            for product in await client.list_public_products(**params):
                product_id = product.get("product_id") or product.get("productId")
                if not product_id:
                    continue
                merged_products[product_id] = product
        return self._select_coinbase_products(list(merged_products.values()))

    @staticmethod
    def _should_skip_coinbase_product_error(exc: Exception) -> bool:
        """Return True when a per-product Coinbase market-data miss should not fail the lane."""
        return isinstance(exc, AdapterError) and exc.status_code == 404

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

    async def capture_jupiter_exact_quote(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        request_direction: str,
    ) -> dict[str, object]:
        """Capture one exact Jupiter quote and return the persisted snapshot id."""
        from d5_trading_engine.adapters.jupiter.client import JupiterClient
        from d5_trading_engine.normalize.jupiter.normalizer import JupiterNormalizer
        from d5_trading_engine.storage.truth.models import QuoteSnapshot, RawJupiterQuoteResponse

        run_id = self._start_ingest_run("jupiter", "quotes")
        start = time.monotonic()
        try:
            client = JupiterClient(self.settings)
            normalizer = JupiterNormalizer(self.settings)
            try:
                requested_at = utcnow()
                request_start = time.monotonic()
                quote = await client.fetch_quote(input_mint, output_mint, amount)
                response_latency_ms = (time.monotonic() - request_start) * 1000
                captured_at = utcnow()
            finally:
                await client.close()

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
            normalizer.normalize_quote(
                quote,
                run_id,
                request_direction=request_direction,
                requested_at=requested_at,
                response_latency_ms=response_latency_ms,
                captured_at=captured_at,
            )
            self._log_health("jupiter", "/swap/v1/quote", True, (time.monotonic() - start) * 1000)
            self._finish_ingest_run(run_id, "success", 1)

            session = get_session(self.settings)
            try:
                snapshot = (
                    session.query(QuoteSnapshot)
                    .filter_by(ingest_run_id=run_id)
                    .order_by(QuoteSnapshot.id.desc())
                    .first()
                )
                if snapshot is None:
                    raise RuntimeError(
                        "Exact Jupiter quote capture finished without a persisted quote_snapshot row."
                    )
                return {
                    "run_id": run_id,
                    "quote_snapshot_id": int(snapshot.id),
                    "request_direction": request_direction,
                }
            finally:
                session.close()
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("jupiter", "/swap/v1/quote", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Jupiter exact quote capture failed: {exc}") from exc

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
        from d5_trading_engine.adapters.helius.ws_client import (
            HeliusWSClient,
            classify_helius_ws_message,
            extract_helius_ws_subscription_id,
            is_helius_ws_notification,
        )
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

            self.raw_store.write_jsonl("helius", "ws_event", messages, run_id)
            self._write_raw_rows(
                RawHeliusWsEvent,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "helius",
                        "subscription_id": extract_helius_ws_subscription_id(message),
                        "event_type": classify_helius_ws_message(message),
                        "payload": orjson.dumps(message).decode(),
                        "captured_at": utcnow(),
                    }
                    for message in messages
                ],
            )

            notification_count = sum(
                1 for message in messages if is_helius_ws_notification(message)
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "transactionSubscribe", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", notification_count)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("helius", "transactionSubscribe", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            raise CaptureError(f"Helius websocket capture failed: {exc}") from exc

        return run_id

    async def capture_coinbase_products(self) -> str:
        """Capture bounded Coinbase spot/futures/perp products into raw and canonical stores."""
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
                products = await self._load_coinbase_context_products(client)
            finally:
                await client.close()

            captured_at = utcnow()
            self.raw_store.write_jsonl("coinbase", "products", products, run_id)
            self._write_coinbase_raw_rows(
                RawCoinbaseProduct,
                [
                    {
                        "ingest_run_id": run_id,
                        "product_id": product.get("product_id") or product.get("productId"),
                        "payload": orjson.dumps(product).decode(),
                        "captured_at": captured_at,
                    }
                    for product in products
                ],
            )

            normalizer = CoinbaseNormalizer(self.settings)
            total_records = normalizer.normalize_products(products)
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
        """Capture Coinbase candles for the bounded context product set."""
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
                products = await self._load_coinbase_context_products(client)
                for product in products:
                    product_id = product.get("product_id") or product.get("productId")
                    if not product_id:
                        continue
                    try:
                        candles = await client.get_public_candles(
                            product_id,
                            limit=self.settings.coinbase_candle_history_minutes,
                        )
                    except Exception as exc:
                        if self._should_skip_coinbase_product_error(exc):
                            log.warning(
                                "coinbase_candle_capture_skipped_product",
                                product_id=product_id,
                                reason=str(exc),
                            )
                            continue
                        raise
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
        """Capture Coinbase recent trade prints for the bounded context product set."""
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
                products = await self._load_coinbase_context_products(client)
                for product in products:
                    product_id = product.get("product_id") or product.get("productId")
                    if not product_id:
                        continue
                    try:
                        trades = await client.get_public_market_trades(product_id)
                    except Exception as exc:
                        if self._should_skip_coinbase_product_error(exc):
                            log.warning(
                                "coinbase_trade_capture_skipped_product",
                                product_id=product_id,
                                reason=str(exc),
                            )
                            continue
                        raise
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
        """Capture Coinbase L2 book snapshots for the bounded context product set."""
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
                products = await self._load_coinbase_context_products(client)
                for product in products:
                    product_id = product.get("product_id") or product.get("productId")
                    if not product_id:
                        continue
                    try:
                        book = await client.get_public_product_book(product_id)
                    except Exception as exc:
                        if self._should_skip_coinbase_product_error(exc):
                            log.warning(
                                "coinbase_book_capture_skipped_product",
                                product_id=product_id,
                                reason=str(exc),
                            )
                            continue
                        raise
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
        """Capture Massive ticker reference rows plus bounded snapshots."""
        from d5_trading_engine.adapters.massive.client import MassiveClient
        from d5_trading_engine.normalize.massive.normalizer import MassiveNormalizer
        from d5_trading_engine.storage.truth.models import RawMassiveCryptoEvent

        run_id = self._start_ingest_run("massive", "crypto_reference")
        start = time.monotonic()

        try:
            client = MassiveClient(self.settings)
            try:
                bundle = await client.fetch_crypto_reference_bundle(
                    list(self.settings.massive_default_tickers)
                )
            finally:
                await client.close()

            captured_at = utcnow()
            reference_rows = bundle.get("tickers", [])
            snapshot_rows = bundle.get("snapshots", [])
            if reference_rows:
                self.raw_store.write_jsonl("massive", "crypto_reference", reference_rows, run_id)
            if snapshot_rows:
                self.raw_store.write_jsonl("massive", "crypto_snapshot", snapshot_rows, run_id)
            raw_rows = [
                {
                    "ingest_run_id": run_id,
                    "provider": "massive",
                    "event_type": "crypto_reference",
                    "payload": orjson.dumps(row).decode(),
                    "captured_at": captured_at,
                }
                for row in reference_rows
            ] + [
                {
                    "ingest_run_id": run_id,
                    "provider": "massive",
                    "event_type": "crypto_snapshot",
                    "payload": orjson.dumps(row).decode(),
                    "captured_at": captured_at,
                }
                for row in snapshot_rows
            ]
            self._write_raw_rows(RawMassiveCryptoEvent, raw_rows)

            normalizer = MassiveNormalizer(self.settings)
            count = normalizer.normalize_reference_tickers(reference_rows)
            for snapshot in snapshot_rows:
                count += normalizer.normalize_snapshot(snapshot, run_id)

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

    async def capture_massive_minute_aggs(
        self,
        date_str: str,
        *,
        allowed_tickers: list[str] | None = None,
        partition: str | None = None,
    ) -> str:
        """Capture a replayable Massive minute-aggregate flat file for one UTC date."""
        from d5_trading_engine.adapters.massive.client import MassiveClient
        from d5_trading_engine.normalize.massive.normalizer import MassiveNormalizer
        from d5_trading_engine.storage.truth.models import RawMassiveCryptoEvent

        run_id = self._start_ingest_run("massive", "minute_aggs")
        start = time.monotonic()

        try:
            client = MassiveClient(self.settings)
            try:
                raw_content = await client.download_minute_aggs(date_str)
                rows = client.parse_minute_aggs_csv(raw_content)
            finally:
                await client.close()

            raw_path = self.raw_store.write_bytes(
                "massive",
                f"minute_aggs_{date_str}",
                raw_content,
                suffix=".csv.gz",
                partition=partition or date_str,
            )
            captured_at = utcnow()
            self._write_raw_rows(
                RawMassiveCryptoEvent,
                [
                    {
                        "ingest_run_id": run_id,
                        "provider": "massive",
                        "event_type": "minute_aggs_flatfile",
                        "payload": orjson.dumps(
                            {
                                "date": date_str,
                                "flatfile_path": str(raw_path),
                                "row_count": len(rows),
                                "normalized_tickers": list(
                                    allowed_tickers or self.settings.massive_default_tickers
                                ),
                            }
                        ).decode(),
                        "captured_at": captured_at,
                    }
                ],
            )
            count = MassiveNormalizer(self.settings).normalize_minute_aggs(
                rows,
                run_id,
                allowed_tickers=allowed_tickers,
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("massive", "minute_aggs_flatfile", True, elapsed_ms)
            self._finish_ingest_run(run_id, "success", count)
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log_health("massive", "minute_aggs_flatfile", False, elapsed_ms, error=str(exc))
            self._finish_ingest_run(run_id, "failed", error=str(exc))
            log.error("massive_minute_aggs_failed_closed", error=str(exc), date=date_str)
            raise CaptureError(f"Massive minute aggregates capture failed closed: {exc}") from exc

        return run_id
