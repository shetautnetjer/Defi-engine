"""Bounded historical Massive minute-aggregate backfill orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import distinct

from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import MarketCandle

_ENTITLEMENT_ASSUMPTION = "massive_free_tier_crypto_minute_2y"


def _parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def _iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


@dataclass(frozen=True)
class MassiveBackfillDayStatus:
    date: str
    action: str
    run_id: str | None = None
    note: str | None = None


class MassiveMinuteAggsBackfill:
    """Backfill a bounded Massive crypto minute-aggregate history window."""

    def __init__(
        self,
        settings: Settings | None = None,
        runner: CaptureRunner | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runner = runner or CaptureRunner(self.settings)

    def resolve_full_free_tier_window(self) -> tuple[str, str]:
        """Resolve the bounded two-year Massive crypto free-tier history window."""
        today_utc = utcnow().date()
        end_date = today_utc - timedelta(days=1)
        start_date = today_utc - timedelta(days=self.settings.massive_free_tier_lookback_days)
        return start_date.isoformat(), end_date.isoformat()

    async def backfill_range(
        self,
        *,
        start_date: str,
        end_date: str,
        resume: bool = True,
        mode: str = "range",
    ) -> dict[str, Any]:
        start = _parse_iso_date(start_date)
        end = _parse_iso_date(end_date)
        if start > end:
            raise RuntimeError(f"Invalid Massive date range: {start_date} > {end_date}")

        batch_id = f"capture_batch_massive_minute_aggs_{uuid.uuid4().hex[:12]}"
        artifact_dir = self.settings.data_dir / "research" / "massive_minute_aggs" / batch_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        expected_tickers = list(self.settings.massive_default_tickers)
        boundary_urls = self._boundary_urls(start_date, end_date)

        statuses: list[MassiveBackfillDayStatus] = []
        for current_day in _iter_dates(start, end):
            current_date_str = current_day.isoformat()
            if resume and self._day_is_complete(current_date_str, expected_tickers):
                statuses.append(
                    MassiveBackfillDayStatus(
                        date=current_date_str,
                        action="skipped",
                        note="raw file and normalized Massive candles already present",
                    )
                )
                continue

            try:
                run_id = await self.runner.capture_massive_minute_aggs(
                    current_date_str,
                    allowed_tickers=expected_tickers,
                    partition=current_date_str,
                )
            except Exception as exc:
                statuses.append(
                    MassiveBackfillDayStatus(
                        date=current_date_str,
                        action="failed",
                        note=str(exc),
                    )
                )
                payload = self._summary_payload(
                    batch_id=batch_id,
                    mode=mode,
                    start_date=start_date,
                    end_date=end_date,
                    resume=resume,
                    statuses=statuses,
                    boundary_urls=boundary_urls,
                    status="failed",
                    error_message=str(exc),
                )
                self._write_artifacts(batch_id=batch_id, artifact_dir=artifact_dir, payload=payload)
                raise

            self.runner.write_capture_receipts(
                run_id,
                context={
                    "requested_provider": "massive-minute-aggs",
                    "date": current_date_str,
                    "capture_batch_id": batch_id,
                },
            )
            statuses.append(
                MassiveBackfillDayStatus(
                    date=current_date_str,
                    action="captured",
                    run_id=run_id,
                )
            )

        payload = self._summary_payload(
            batch_id=batch_id,
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            resume=resume,
            statuses=statuses,
            boundary_urls=boundary_urls,
            status="success",
            error_message=None,
        )
        self._write_artifacts(batch_id=batch_id, artifact_dir=artifact_dir, payload=payload)
        return payload

    async def backfill_full_free_tier(self, *, resume: bool = True) -> dict[str, Any]:
        start_date, end_date = self.resolve_full_free_tier_window()
        return await self.backfill_range(
            start_date=start_date,
            end_date=end_date,
            resume=resume,
            mode="full_free_tier",
        )

    def _boundary_urls(self, start_date: str, end_date: str) -> dict[str, str]:
        from d5_trading_engine.adapters.massive.client import MassiveClient

        client = MassiveClient(self.settings)
        return {
            "oldest_requested_url": client.build_minute_aggs_url(start_date),
            "newest_requested_url": client.build_minute_aggs_url(end_date),
        }

    def _day_is_complete(self, date_str: str, expected_tickers: list[str]) -> bool:
        raw_dir = self.settings.raw_dir / "massive" / date_str
        raw_present = any(raw_dir.glob(f"minute_aggs_{date_str}_*.csv.gz"))
        if not raw_present:
            return False

        expected_ticker_set = {ticker.upper() for ticker in expected_tickers}
        session = get_session(self.settings)
        try:
            rows = (
                session.query(distinct(MarketCandle.product_id))
                .filter_by(
                    venue="massive",
                    granularity="ONE_MINUTE",
                    event_date_utc=date_str,
                )
                .filter(MarketCandle.product_id.in_(expected_tickers))
                .all()
            )
        finally:
            session.close()

        normalized_tickers = {str(product_id).upper() for (product_id,) in rows}
        return normalized_tickers == expected_ticker_set

    def _summary_payload(
        self,
        *,
        batch_id: str,
        mode: str,
        start_date: str,
        end_date: str,
        resume: bool,
        statuses: list[MassiveBackfillDayStatus],
        boundary_urls: dict[str, str],
        status: str,
        error_message: str | None,
    ) -> dict[str, Any]:
        captured = [row for row in statuses if row.action == "captured"]
        skipped = [row for row in statuses if row.action == "skipped"]
        failed = [row for row in statuses if row.action == "failed"]
        return {
            "batch_id": batch_id,
            "capture_type": "massive-minute-aggs",
            "status": status,
            "error_message": error_message,
            "mode": mode,
            "resume": resume,
            "entitlement_assumption": _ENTITLEMENT_ASSUMPTION,
            "resolved_start_date": start_date,
            "resolved_end_date": end_date,
            "lookback_days": (
                self.settings.massive_free_tier_lookback_days
                if mode == "full_free_tier"
                else ((_parse_iso_date(end_date) - _parse_iso_date(start_date)).days + 1)
            ),
            "default_tickers": list(self.settings.massive_default_tickers),
            "boundary_verification": {
                "oldest_requested_day": start_date,
                "newest_requested_day": end_date,
                **boundary_urls,
            },
            "days": {
                "requested_count": len(statuses),
                "captured_count": len(captured),
                "skipped_count": len(skipped),
                "failed_count": len(failed),
            },
            "captured_runs": [
                {"date": row.date, "run_id": row.run_id}
                for row in captured
            ],
            "skipped_days": [
                {"date": row.date, "note": row.note}
                for row in skipped
            ],
            "failed_days": [
                {"date": row.date, "note": row.note}
                for row in failed
            ],
            "recommended_next_step": (
                "Re-materialize global-regime-inputs-15m-v1 and rerun shadow comparison on "
                "the bounded historical window."
                if status == "success"
                else "Fix the first failed Massive day before trusting the historical ladder."
            ),
            "generated_at": utcnow().isoformat(),
        }

    def _write_artifacts(self, *, batch_id: str, artifact_dir: Path, payload: dict[str, Any]) -> None:
        owner_type = "capture_batch"
        owner_key = batch_id
        history_window = {
            "entitlement_assumption": payload["entitlement_assumption"],
            "resolved_start_date": payload["resolved_start_date"],
            "resolved_end_date": payload["resolved_end_date"],
            "lookback_days": payload["lookback_days"],
            "boundary_verification": payload["boundary_verification"],
        }
        write_json_artifact(
            artifact_dir / "config.json",
            {
                "batch_id": batch_id,
                "mode": payload["mode"],
                "resume": payload["resume"],
                "default_tickers": payload["default_tickers"],
            },
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="massive_minute_aggs_backfill_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "history_window.json",
            history_window,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="massive_minute_aggs_history_window",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "capture_summary.json",
            payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="massive_minute_aggs_backfill_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "capture_run.qmd",
                title="massive_minute_aggs_backfill",
                summary_lines=[
                    f"- batch id: `{batch_id}`",
                    f"- status: `{payload['status']}`",
                    f"- mode: `{payload['mode']}`",
                    f"- start date: `{payload['resolved_start_date']}`",
                    f"- end date: `{payload['resolved_end_date']}`",
                    f"- requested days: `{payload['days']['requested_count']}`",
                    f"- captured days: `{payload['days']['captured_count']}`",
                    f"- skipped days: `{payload['days']['skipped_count']}`",
                    f"- failed days: `{payload['days']['failed_count']}`",
                ],
                sections=[
                    (
                        "History Window",
                        [
                            f"- entitlement assumption: `{payload['entitlement_assumption']}`",
                            f"- oldest requested day: `{payload['boundary_verification']['oldest_requested_day']}`",
                            f"- newest requested day: `{payload['boundary_verification']['newest_requested_day']}`",
                            f"- oldest requested url: `{payload['boundary_verification']['oldest_requested_url']}`",
                            f"- newest requested url: `{payload['boundary_verification']['newest_requested_url']}`",
                        ],
                    ),
                    (
                        "Captured Runs",
                        [
                            f"- `{row['date']}` -> `{row['run_id']}`"
                            for row in payload["captured_runs"]
                        ]
                        or ["- none"],
                    ),
                    (
                        "Skipped Days",
                        [
                            f"- `{row['date']}`: {row['note']}"
                            for row in payload["skipped_days"]
                        ]
                        or ["- none"],
                    ),
                    (
                        "Failures",
                        [
                            f"- `{row['date']}`: {row['note']}"
                            for row in payload["failed_days"]
                        ]
                        or ["- none"],
                    ),
                    ("Next Step", [str(payload["recommended_next_step"])]),
                ],
            ),
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="massive_minute_aggs_backfill_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
