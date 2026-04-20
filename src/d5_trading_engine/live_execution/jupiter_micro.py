"""Guarded Jupiter micro-live swap executor."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import orjson

from d5_trading_engine.config.settings import Settings
from d5_trading_engine.live_execution.arm_state import MicroLiveArmStore
from d5_trading_engine.live_execution.readiness import LiveReadinessService
from d5_trading_engine.live_execution.signer import ExternalCommandSigner, TransactionSigner


class JupiterMicroLiveExecutor:
    """Execute one gated Jupiter order/execute swap with external signing."""

    def __init__(
        self,
        *,
        settings: Settings,
        signer: TransactionSigner | None = None,
        http_client: httpx.AsyncClient | None = None,
        readiness_service: LiveReadinessService | None = None,
        arm_store: MicroLiveArmStore | None = None,
    ) -> None:
        self.settings = settings
        self.signer = signer or ExternalCommandSigner(settings)
        self.http_client = http_client
        self.readiness_service = readiness_service or LiveReadinessService(settings)
        self.arm_store = arm_store or MicroLiveArmStore(settings)

    async def execute_swap(
        self,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int = 50,
    ) -> dict[str, Any]:
        """Run one Jupiter micro-live swap if every local safety gate passes."""

        if self.settings.micro_live_kill_switch:
            return self._blocked(["micro_live_kill_switch_active"])

        readiness = self.readiness_service.evaluate()
        if not readiness.get("passed"):
            return self._blocked(["live_readiness_not_passed"], readiness=readiness)

        arm_status = self.arm_store.status()
        if not arm_status.get("armed"):
            return self._blocked(arm_status.get("reason_codes", ["micro_live_not_armed"]))

        cap_reason = self._notional_cap_reason(input_mint, amount, arm_status)
        if cap_reason is not None:
            return self._blocked([cap_reason], arm_status=arm_status)

        taker = getattr(self.signer, "signer_pubkey", "")
        if not taker:
            return self._blocked(["micro_live_signer_pubkey_missing"])

        owns_client = self.http_client is None
        client = self.http_client or self._new_client()
        try:
            order = await self._order(
                client,
                input_mint=input_mint,
                output_mint=output_mint,
                amount=amount,
                slippage_bps=slippage_bps,
                taker=taker,
            )
            unsigned_transaction = str(order.get("transaction") or "")
            request_id = str(order.get("requestId") or order.get("request_id") or "")
            if not unsigned_transaction or not request_id:
                return self._blocked(["jupiter_order_missing_transaction"], order=order)

            signed = self.signer.sign(unsigned_transaction, request_id=request_id)
            execution = await self._execute(
                client,
                signed_transaction=signed.signed_transaction,
                request_id=request_id,
            )
        finally:
            if owns_client:
                await client.aclose()

        status = str(execution.get("status") or "").lower()
        signature = str(execution.get("signature") or "")
        result = {
            "status": "success" if status == "success" and signature else "failed",
            "reason_codes": [] if signature else ["jupiter_execute_missing_signature"],
            "signature": signature,
            "request_id": request_id,
            "input_mint": input_mint,
            "output_mint": output_mint,
            "amount": amount,
            "slippage_bps": slippage_bps,
            "order": self._safe_order_receipt(order),
            "execution": execution,
            "executed_at_utc": datetime.now(UTC).isoformat(),
        }
        self._append_ledger(result)
        return result

    def _new_client(self) -> httpx.AsyncClient:
        headers = {}
        if self.settings.jupiter_api_key:
            headers["x-api-key"] = self.settings.jupiter_api_key
        return httpx.AsyncClient(
            base_url=self.settings.jupiter_swap_v2_base,
            headers=headers,
            timeout=30.0,
        )

    async def _order(
        self,
        client: httpx.AsyncClient,
        *,
        input_mint: str,
        output_mint: str,
        amount: int,
        slippage_bps: int,
        taker: str,
    ) -> dict[str, Any]:
        response = await client.get(
            "/swap/v2/order",
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": str(amount),
                "slippageBps": str(slippage_bps),
                "taker": taker,
            },
        )
        response.raise_for_status()
        return response.json()

    async def _execute(
        self,
        client: httpx.AsyncClient,
        *,
        signed_transaction: str,
        request_id: str,
    ) -> dict[str, Any]:
        response = await client.post(
            "/swap/v2/execute",
            json={
                "signedTransaction": signed_transaction,
                "requestId": request_id,
            },
        )
        response.raise_for_status()
        return response.json()

    def _notional_cap_reason(
        self,
        input_mint: str,
        amount: int,
        arm_status: dict[str, Any],
    ) -> str | None:
        if input_mint != self.settings.usdc_mint:
            return None
        amount_usdc = amount / 1_000_000
        if amount_usdc > float(arm_status.get("max_notional_usdc", 0.0)):
            return "micro_live_notional_above_arm_cap"
        return None

    def _append_ledger(self, result: dict[str, Any]) -> None:
        path = self._ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(orjson.dumps(result))
            handle.write(b"\n")

    def _ledger_path(self) -> Path:
        return self.settings.data_dir / "live_execution" / "micro_live_ledger.jsonl"

    def _blocked(self, reason_codes: list[str], **extra: Any) -> dict[str, Any]:
        return {
            "status": "blocked",
            "reason_codes": reason_codes,
            "executed_at_utc": datetime.now(UTC).isoformat(),
            **extra,
        }

    def _safe_order_receipt(self, order: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in order.items()
            if key not in {"transaction", "signedTransaction"}
        }

