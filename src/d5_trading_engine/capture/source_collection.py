"""Incremental background source collection over cached historical truth."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from d5_trading_engine.capture.massive_backfill import MassiveMinuteAggsBackfill
from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata


class BackgroundSourceCollector:
    """Own bounded source accumulation without repulling cached history."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.runner = CaptureRunner(self.settings)
        self.backfill = MassiveMinuteAggsBackfill(self.settings, runner=self.runner)

    async def collect_incremental(
        self,
        *,
        max_massive_days: int = 1,
        include_helius: bool = False,
        include_jupiter: bool = True,
    ) -> dict[str, Any]:
        collect_id = f"source_collection_{utcnow().strftime('%Y%m%dT%H%M%S%fZ')}"
        artifact_dir = self.settings.data_dir / "research" / "source_collection" / collect_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        historical_before = self.backfill.historical_cache_status()
        massive_result = await self.backfill.backfill_missing_full_free_tier(
            max_days=max_massive_days,
            resume=True,
        )
        historical_after = self.backfill.historical_cache_status()

        capture_steps: list[dict[str, Any]] = []
        if include_jupiter:
            for label, capture_fn in (
                ("jupiter-prices", self.runner.capture_jupiter_prices),
                ("jupiter-quotes", self.runner.capture_jupiter_quotes),
            ):
                run_id = await capture_fn()
                self.runner.write_capture_receipts(
                    run_id,
                    context={"requested_provider": label, "source_collection_id": collect_id},
                )
                capture_steps.append({"lane": label, "run_id": run_id})

        if include_helius:
            for label, capture_fn in (
                ("helius-transactions", self.runner.capture_helius_transactions),
                ("helius-discovery", self.runner.capture_helius_discovery),
            ):
                run_id = await capture_fn()
                self.runner.write_capture_receipts(
                    run_id,
                    context={"requested_provider": label, "source_collection_id": collect_id},
                )
                capture_steps.append({"lane": label, "run_id": run_id})

        for label, capture_fn in (
            ("coinbase-products", self.runner.capture_coinbase_products),
            ("coinbase-candles", self.runner.capture_coinbase_candles),
            ("coinbase-book", self.runner.capture_coinbase_book),
            ("coinbase-market-trades", self.runner.capture_coinbase_market_trades),
        ):
            run_id = await capture_fn()
            self.runner.write_capture_receipts(
                run_id,
                context={"requested_provider": label, "source_collection_id": collect_id},
            )
            capture_steps.append({"lane": label, "run_id": run_id})

        payload = {
            "collect_id": collect_id,
            "status": "completed",
            "artifact_dir": str(artifact_dir),
            "historical_cache_before": historical_before,
            "historical_cache_after": historical_after,
            "massive_result": massive_result,
            "capture_steps": capture_steps,
            "include_helius": bool(include_helius),
            "include_jupiter": bool(include_jupiter),
            "next_command": "d5 training status --json",
            "generated_at": utcnow().isoformat(),
        }
        self._write_artifacts(collect_id=collect_id, artifact_dir=artifact_dir, payload=payload)
        self._write_status_receipt(payload)
        return payload

    def _write_artifacts(self, *, collect_id: str, artifact_dir: Path, payload: dict[str, Any]) -> None:
        owner_type = "source_collection"
        owner_key = collect_id
        write_json_artifact(
            artifact_dir / "config.json",
            {
                "collect_id": collect_id,
                "include_helius": payload["include_helius"],
                "include_jupiter": payload["include_jupiter"],
                "next_command": payload["next_command"],
            },
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="source_collection_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "summary.json",
            payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="source_collection_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "capture_run.qmd",
                title="source_collection",
                metadata=trading_report_metadata(
                    report_kind="source_collection",
                    run_id=collect_id,
                    owner_type=owner_type,
                    owner_key=owner_key,
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="15m",
                    summary_path="summary.json",
                    config_path="config.json",
                ),
                summary_lines=[
                    f"- collect id: `{collect_id}`",
                    f"- historical cache complete before: `{payload['historical_cache_before']['complete']}`",
                    f"- historical cache complete after: `{payload['historical_cache_after']['complete']}`",
                    f"- capture steps: `{len(payload['capture_steps'])}`",
                ],
                sections=[
                    (
                        "Historical Cache",
                        [
                            f"- next missing before: `{payload['historical_cache_before']['next_missing_date'] or 'none'}`",
                            f"- next missing after: `{payload['historical_cache_after']['next_missing_date'] or 'none'}`",
                            f"- completed days after: `{payload['historical_cache_after']['completed_day_count']}`",
                        ],
                    ),
                    (
                        "Market / Source Context",
                        [
                            "- storage contract: raw `CSV.gz` + partitioned `Parquet` + normalized `SQL`",
                            f"- status: `{payload['massive_result']['status']}`",
                            f"- requested days: `{payload['massive_result']['days']['requested_count']}`",
                            f"- captured days: `{payload['massive_result']['days']['captured_count']}`",
                            f"- skipped days: `{payload['massive_result']['days']['skipped_count']}`",
                        ],
                    ),
                    (
                        "Capture Steps",
                        [
                            f"- `{row['lane']}` -> `{row['run_id']}`"
                            for row in payload["capture_steps"]
                        ] or ["- none"],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="source_collection_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

    def _write_status_receipt(self, payload: dict[str, Any]) -> None:
        state_dir = self.settings.repo_root / ".ai" / "dropbox" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        write_json_artifact(
            state_dir / "source_collection_status.json",
            payload,
            owner_type="source_collection",
            owner_key=str(payload["collect_id"]),
            artifact_type="source_collection_status_receipt",
            settings=self.settings,
        )
