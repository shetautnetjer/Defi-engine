from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import orjson
import pytest

from d5_trading_engine.cli import cli
from d5_trading_engine.config.settings import Settings
from d5_trading_engine.live_execution.arm_state import MicroLiveArmStore
from d5_trading_engine.live_execution.jupiter_micro import JupiterMicroLiveExecutor
from d5_trading_engine.live_execution.readiness import LiveReadinessService
from d5_trading_engine.live_execution.signer import SignedTransaction, TransactionSigner


def _write_readiness_metrics(settings: Settings, **overrides: object) -> None:
    metrics = {
        "rolling_win_rate": 0.82,
        "settled_trades": 24,
        "average_settled_trades_per_week": 1.2,
        "consecutive_trade_weeks": 4,
        "net_expectancy_after_cost": 0.18,
        "profit_factor": 1.7,
        "max_drawdown_pct": 2.5,
        "quote_health_ok": True,
        "unexplained_decision_gap_count": 0,
        "candidate_comparison_accepted": True,
    }
    metrics.update(overrides)
    path = settings.data_dir / "research" / "training" / "live_readiness" / "latest_metrics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(orjson.dumps(metrics, option=orjson.OPT_INDENT_2))


def test_live_readiness_fails_closed_without_metrics(settings: Settings) -> None:
    result = LiveReadinessService(settings).evaluate()

    assert result["passed"] is False
    assert result["status"] == "failed"
    assert "live_readiness_metrics_missing" in result["reason_codes"]


def test_live_readiness_requires_win_rate_and_trade_frequency(settings: Settings) -> None:
    _write_readiness_metrics(
        settings,
        rolling_win_rate=0.79,
        consecutive_trade_weeks=3,
    )

    result = LiveReadinessService(settings).evaluate()

    assert result["passed"] is False
    assert "rolling_win_rate_below_minimum" in result["reason_codes"]
    assert "consecutive_trade_weeks_below_minimum" in result["reason_codes"]


def test_live_readiness_passes_with_micro_live_gate_metrics(settings: Settings) -> None:
    _write_readiness_metrics(settings)

    result = LiveReadinessService(settings).evaluate()

    assert result["passed"] is True
    assert result["status"] == "passed"
    assert result["micro_live_candidate"] is True
    assert result["thresholds"]["minimum_rolling_win_rate"] == 0.8


def test_micro_live_arm_requires_passing_readiness(settings: Settings) -> None:
    store = MicroLiveArmStore(settings)

    readiness = LiveReadinessService(settings).evaluate()
    result = store.arm(
        readiness=readiness,
        max_notional_usdc=2.0,
        daily_loss_limit_usdc=1.0,
        weekly_loss_limit_usdc=2.0,
    )

    assert result["armed"] is False
    assert "live_readiness_not_passed" in result["reason_codes"]


def test_micro_live_arm_writes_expiring_armed_state(settings: Settings) -> None:
    _write_readiness_metrics(settings)
    readiness = LiveReadinessService(settings).evaluate()

    result = MicroLiveArmStore(settings).arm(
        readiness=readiness,
        max_notional_usdc=2.0,
        daily_loss_limit_usdc=1.0,
        weekly_loss_limit_usdc=2.0,
        ttl_minutes=30,
    )

    assert result["armed"] is True
    assert result["max_notional_usdc"] == 2.0
    assert result["expires_at_utc"] > result["armed_at_utc"]


class _FakeSigner(TransactionSigner):
    signer_pubkey = "FakeTaker111111111111111111111111111111111111"

    def sign(self, unsigned_transaction: str, *, request_id: str) -> SignedTransaction:
        assert unsigned_transaction == "unsigned-tx"
        assert request_id == "request-1"
        return SignedTransaction(
            signed_transaction="signed-tx",
            signer_pubkey=self.signer_pubkey,
        )


@pytest.mark.asyncio
async def test_micro_live_executor_requires_arm_state(settings: Settings) -> None:
    _write_readiness_metrics(settings)

    executor = JupiterMicroLiveExecutor(settings=settings, signer=_FakeSigner())
    result = await executor.execute_swap(
        input_mint=settings.usdc_mint,
        output_mint=settings.sol_mint,
        amount=1_000_000,
    )

    assert result["status"] == "blocked"
    assert "micro_live_not_armed" in result["reason_codes"]


@pytest.mark.asyncio
async def test_micro_live_executor_uses_jupiter_order_execute_and_writes_ledger(
    settings: Settings,
) -> None:
    _write_readiness_metrics(settings)
    readiness = LiveReadinessService(settings).evaluate()
    MicroLiveArmStore(settings).arm(
        readiness=readiness,
        max_notional_usdc=2.0,
        daily_loss_limit_usdc=1.0,
        weekly_loss_limit_usdc=2.0,
    )

    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/swap/v2/order":
            assert request.url.params["taker"] == _FakeSigner.signer_pubkey
            assert request.url.params["amount"] == "1000000"
            return httpx.Response(
                200,
                json={
                    "transaction": "unsigned-tx",
                    "requestId": "request-1",
                    "outAmount": "950000000",
                    "router": "iris",
                    "mode": "ultra",
                    "feeBps": 2,
                    "feeMint": settings.usdc_mint,
                },
            )
        if request.url.path == "/swap/v2/execute":
            payload = orjson.loads(request.content)
            assert payload == {"signedTransaction": "signed-tx", "requestId": "request-1"}
            return httpx.Response(
                200,
                json={
                    "status": "Success",
                    "signature": "5sig",
                    "code": 0,
                    "inputAmountResult": "1000000",
                    "outputAmountResult": "950000000",
                },
            )
        return httpx.Response(404, json={"error": "unexpected path"})

    async with httpx.AsyncClient(
        base_url=settings.jupiter_swap_v2_base,
        transport=httpx.MockTransport(handler),
    ) as client:
        result = await JupiterMicroLiveExecutor(
            settings=settings,
            signer=_FakeSigner(),
            http_client=client,
        ).execute_swap(
            input_mint=settings.usdc_mint,
            output_mint=settings.sol_mint,
            amount=1_000_000,
        )

    assert result["status"] == "success"
    assert result["signature"] == "5sig"
    assert seen_paths == ["/swap/v2/order", "/swap/v2/execute"]

    ledger_path = settings.data_dir / "live_execution" / "micro_live_ledger.jsonl"
    ledger_lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert len(ledger_lines) == 1
    ledger_entry = orjson.loads(ledger_lines[0])
    assert ledger_entry["signature"] == "5sig"
    assert "private" not in ledger_lines[0].lower()


def test_arm_state_expires(settings: Settings) -> None:
    _write_readiness_metrics(settings)
    readiness = LiveReadinessService(settings).evaluate()
    store = MicroLiveArmStore(settings)
    store.arm(
        readiness=readiness,
        max_notional_usdc=2.0,
        daily_loss_limit_usdc=1.0,
        weekly_loss_limit_usdc=2.0,
    )

    later = datetime.now(UTC) + timedelta(hours=2)

    assert store.status(now=later)["armed"] is False
    assert "micro_live_arm_expired" in store.status(now=later)["reason_codes"]


def test_live_readiness_cli_fails_closed_without_metrics(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["live-readiness", "--json"])

    assert result.exit_code == 0
    payload = orjson.loads(result.output)
    assert payload["passed"] is False
    assert "live_readiness_metrics_missing" in payload["reason_codes"]


def test_micro_live_status_cli_reports_not_armed(cli_runner) -> None:
    result = cli_runner.invoke(cli, ["micro-live", "status", "--json"])

    assert result.exit_code == 0
    payload = orjson.loads(result.output)
    assert payload["armed"] is False
    assert "micro_live_not_armed" in payload["reason_codes"]
