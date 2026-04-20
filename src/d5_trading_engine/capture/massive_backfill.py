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
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata
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

    def historical_cache_status(self) -> dict[str, Any]:
        """Return bounded cache completeness for the fixed free-tier history window."""
        start_date, end_date = self.resolve_full_free_tier_window()
        expected_tickers = list(self.settings.massive_default_tickers)
        completed_days: list[str] = []
        missing_days: list[str] = []
        for current_day in _iter_dates(_parse_iso_date(start_date), _parse_iso_date(end_date)):
            day_str = current_day.isoformat()
            if self._day_is_complete(day_str, expected_tickers):
                completed_days.append(day_str)
            else:
                missing_days.append(day_str)

        return {
            "entitlement_assumption": _ENTITLEMENT_ASSUMPTION,
            "resolved_start_date": start_date,
            "resolved_end_date": end_date,
            "default_tickers": expected_tickers,
            "requested_day_count": len(completed_days) + len(missing_days),
            "completed_day_count": len(completed_days),
            "missing_day_count": len(missing_days),
            "complete": len(missing_days) == 0,
            "earliest_completed_date": completed_days[0] if completed_days else "",
            "latest_completed_date": completed_days[-1] if completed_days else "",
            "next_missing_date": missing_days[0] if missing_days else "",
        }

    async def backfill_missing_full_free_tier(
        self,
        *,
        max_days: int | None = None,
        resume: bool = True,
    ) -> dict[str, Any]:
        """Backfill only the missing segment of the bounded free-tier window."""
        cache_status = self.historical_cache_status()
        if cache_status["complete"]:
            return {
                "batch_id": "",
                "capture_type": "massive-minute-aggs",
                "status": "noop",
                "mode": "incremental_missing",
                "resume": resume,
                "entitlement_assumption": _ENTITLEMENT_ASSUMPTION,
                "resolved_start_date": cache_status["resolved_start_date"],
                "resolved_end_date": cache_status["resolved_end_date"],
                "days": {
                    "requested_count": 0,
                    "captured_count": 0,
                    "skipped_count": int(cache_status["completed_day_count"]),
                    "failed_count": 0,
                },
                "historical_cache_status": cache_status,
                "recommended_next_step": "Continue with incremental live/source collection only.",
                "generated_at": utcnow().isoformat(),
            }

        start = _parse_iso_date(str(cache_status["next_missing_date"]))
        end = _parse_iso_date(str(cache_status["resolved_end_date"]))
        if max_days is not None and max_days > 0:
            bounded_end = start + timedelta(days=max_days - 1)
            end = min(end, bounded_end)
        return await self.backfill_range(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            resume=resume,
            mode="incremental_missing",
        )

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

        statuses = self._iter_missing_windows(
            start_date=start_date,
            end_date=end_date,
            resume=resume,
            expected_tickers=expected_tickers,
        )
        status_by_date = {row.date: row for row in statuses}
        range_chunks: list[dict[str, Any]] = []
        chunk_failure: str | None = None

        for chunk_start, chunk_end, chunk_dates in self._pending_range_chunks(statuses):
            try:
                result = await self.runner.capture_massive_minute_aggs_range(
                    chunk_start,
                    chunk_end,
                    allowed_tickers=expected_tickers,
                )
                run_id = str(result.get("run_id") or "")
                captured_dates = {
                    str(item) for item in result.get("captured_dates", []) if item
                }
                self.runner.write_capture_receipts(
                    run_id,
                    context={
                        "requested_provider": "massive-minute-aggs",
                        "date_range": {"start_date": chunk_start, "end_date": chunk_end},
                        "capture_batch_id": batch_id,
                    },
                )
                for date_str in chunk_dates:
                    if date_str in captured_dates:
                        status_by_date[date_str] = MassiveBackfillDayStatus(
                            date=date_str,
                            action="captured",
                            run_id=run_id,
                        )
                    else:
                        status_by_date[date_str] = MassiveBackfillDayStatus(
                            date=date_str,
                            action="failed",
                            run_id=run_id,
                            note="range capture did not return rows for this day",
                        )
                range_chunks.append(
                    {
                        "start_date": chunk_start,
                        "end_date": chunk_end,
                        "requested_dates": chunk_dates,
                        "captured_dates": sorted(captured_dates),
                        "run_id": run_id,
                        "row_count": int(result.get("row_count") or 0),
                        "status": "captured",
                    }
                )
            except Exception as exc:
                chunk_failure = str(exc)
                for date_str in chunk_dates:
                    status_by_date[date_str] = MassiveBackfillDayStatus(
                        date=date_str,
                        action="failed",
                        note=chunk_failure,
                    )
                range_chunks.append(
                    {
                        "start_date": chunk_start,
                        "end_date": chunk_end,
                        "requested_dates": chunk_dates,
                        "captured_dates": [],
                        "run_id": "",
                        "row_count": 0,
                        "status": "failed",
                        "error_message": chunk_failure,
                    }
                )
                payload = self._summary_payload(
                    batch_id=batch_id,
                    mode=mode,
                    start_date=start_date,
                    end_date=end_date,
                    resume=resume,
                    statuses=[status_by_date[row.date] for row in statuses],
                    boundary_urls=boundary_urls,
                    status="failed",
                    error_message=chunk_failure,
                    range_chunks=range_chunks,
                )
                self._attach_artifact_metadata(payload=payload, artifact_dir=artifact_dir)
                self._write_artifacts(batch_id=batch_id, artifact_dir=artifact_dir, payload=payload)
                raise

        payload = self._summary_payload(
            batch_id=batch_id,
            mode=mode,
            start_date=start_date,
            end_date=end_date,
            resume=resume,
            statuses=[status_by_date[row.date] for row in statuses],
            boundary_urls=boundary_urls,
            status="failed" if chunk_failure else "success",
            error_message=chunk_failure,
            range_chunks=range_chunks,
        )
        self._attach_artifact_metadata(payload=payload, artifact_dir=artifact_dir)
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

    async def backfill_missing_full_free_tier(
        self,
        *,
        max_days: int | None = None,
        resume: bool = True,
    ) -> dict[str, Any]:
        cache_status = self.historical_cache_status()
        if cache_status["complete"]:
            start_date = cache_status["resolved_start_date"]
            end_date = cache_status["resolved_end_date"]
            return {
                "status": "noop",
                "batch_id": "historical_cache_complete",
                "mode": "incremental_missing",
                "resume": resume,
                "entitlement_assumption": _ENTITLEMENT_ASSUMPTION,
                "resolved_start_date": start_date,
                "resolved_end_date": end_date,
                "lookback_days": self.settings.massive_free_tier_lookback_days,
                "default_tickers": list(self.settings.massive_default_tickers),
                "days": {
                    "requested_count": 0,
                    "captured_count": 0,
                    "skipped_count": 0,
                    "failed_count": 0,
                },
                "captured_runs": [],
                "skipped_days": [],
                "failed_days": [],
                "historical_cache_before": cache_status,
                "historical_cache_after": cache_status,
                "recommended_next_step": (
                    "Historical Massive cache is already complete. "
                    "Use incremental source collection instead of repulling history."
                ),
                "generated_at": utcnow().isoformat(),
            }

        start_date = _parse_iso_date(cache_status["next_missing_date"])
        end_date = _parse_iso_date(cache_status["resolved_end_date"])
        if max_days is not None:
            if max_days <= 0:
                raise RuntimeError("max_days must be positive when provided.")
            bounded_end = start_date + timedelta(days=max_days - 1)
            end_date = min(end_date, bounded_end)

        return await self.backfill_range(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            resume=resume,
            mode="incremental_missing",
        )

    def historical_cache_status(self) -> dict[str, Any]:
        start_date, end_date = self.resolve_full_free_tier_window()
        start = _parse_iso_date(start_date)
        end = _parse_iso_date(end_date)
        expected_tickers = list(self.settings.massive_default_tickers)
        expected_count = len(expected_tickers)
        expected_ticker_set = {ticker.upper() for ticker in expected_tickers}
        normalized_by_date = self._normalized_tickers_by_date(
            start_date=start_date,
            end_date=end_date,
            expected_tickers=expected_tickers,
        )

        completed_dates: list[str] = []
        next_missing_date: str | None = None
        for current_day in _iter_dates(start, end):
            current_date_str = current_day.isoformat()
            raw_present = self._raw_day_present(current_date_str)
            parquet_present = self._parquet_day_present(current_date_str)
            normalized_tickers = normalized_by_date.get(current_date_str, set())
            if raw_present and parquet_present and normalized_tickers == expected_ticker_set:
                completed_dates.append(current_date_str)
                continue
            if next_missing_date is None:
                next_missing_date = current_date_str

        requested_day_count = (end - start).days + 1
        completed_day_count = len(completed_dates)
        missing_day_count = max(0, requested_day_count - completed_day_count)
        return {
            "entitlement_assumption": _ENTITLEMENT_ASSUMPTION,
            "resolved_start_date": start_date,
            "resolved_end_date": end_date,
            "default_tickers": expected_tickers,
            "expected_ticker_count": expected_count,
            "requested_day_count": requested_day_count,
            "completed_day_count": completed_day_count,
            "parquet_complete_day_count": completed_day_count,
            "missing_day_count": missing_day_count,
            "complete": missing_day_count == 0,
            "earliest_completed_date": completed_dates[0] if completed_dates else "",
            "latest_completed_date": completed_dates[-1] if completed_dates else "",
            "next_missing_date": next_missing_date or "",
            "generated_at": utcnow().isoformat(),
        }

    def _iter_missing_windows(
        self,
        *,
        start_date: str,
        end_date: str,
        resume: bool = True,
        expected_tickers: list[str] | None = None,
    ) -> list[MassiveBackfillDayStatus]:
        """Resolve per-day actions for a bounded Massive history window."""
        expected = list(expected_tickers or self.settings.massive_default_tickers)
        statuses: list[MassiveBackfillDayStatus] = []
        for current_day in _iter_dates(_parse_iso_date(start_date), _parse_iso_date(end_date)):
            current_date_str = current_day.isoformat()
            if resume and self._day_is_complete(current_date_str, expected):
                statuses.append(
                    MassiveBackfillDayStatus(
                        date=current_date_str,
                        action="skipped",
                        note="raw file, parquet partition, and normalized Massive candles already present",
                    )
                )
            else:
                statuses.append(MassiveBackfillDayStatus(date=current_date_str, action="pending"))
        return statuses

    def _pending_range_chunks(
        self,
        statuses: list[MassiveBackfillDayStatus],
    ) -> list[tuple[str, str, list[str]]]:
        """Group contiguous pending days into REST range chunks."""
        max_days = max(1, int(self.settings.massive_rest_minute_aggs_range_chunk_days))
        chunks: list[tuple[str, str, list[str]]] = []
        pending_dates: list[str] = []
        previous_date: date | None = None

        def _flush() -> None:
            nonlocal pending_dates
            while pending_dates:
                chunk_dates = pending_dates[:max_days]
                pending_dates = pending_dates[max_days:]
                chunks.append((chunk_dates[0], chunk_dates[-1], chunk_dates))

        for status in statuses:
            if status.action != "pending":
                _flush()
                previous_date = None
                continue
            current_date = _parse_iso_date(status.date)
            if previous_date is not None and current_date != previous_date + timedelta(days=1):
                _flush()
            pending_dates.append(status.date)
            previous_date = current_date
        _flush()
        return chunks

    def _raw_day_present(self, date_str: str) -> bool:
        raw_dir = self.settings.raw_dir / "massive" / date_str
        return any(raw_dir.glob(f"minute_aggs_{date_str}_*"))

    def _parquet_day_present(self, date_str: str) -> bool:
        parquet_dir = (
            self.settings.parquet_dir
            / "massive"
            / "global_crypto"
            / "minute_aggs_v1"
            / f"date={date_str}"
        )
        return any(parquet_dir.glob("minute_aggs_*.parquet"))

    def _normalized_tickers_by_date(
        self,
        *,
        start_date: str,
        end_date: str,
        expected_tickers: list[str],
    ) -> dict[str, set[str]]:
        session = get_session(self.settings)
        try:
            rows = (
                session.query(MarketCandle.event_date_utc, MarketCandle.product_id)
                .filter_by(venue="massive", granularity="ONE_MINUTE")
                .filter(MarketCandle.product_id.in_(expected_tickers))
                .filter(MarketCandle.event_date_utc >= start_date)
                .filter(MarketCandle.event_date_utc <= end_date)
                .distinct()
                .all()
            )
        finally:
            session.close()

        normalized_by_date: dict[str, set[str]] = {}
        for event_date_utc, product_id in rows:
            normalized_by_date.setdefault(str(event_date_utc), set()).add(str(product_id).upper())
        return normalized_by_date

    def _boundary_urls(self, start_date: str, end_date: str) -> dict[str, str]:
        from d5_trading_engine.adapters.massive.client import MassiveClient

        client = MassiveClient(self.settings)
        sample_ticker = self.settings.massive_default_tickers[0]
        return {
            "historical_source_mode": "flat_files_first_with_rest_incremental_fallback",
            "flatfile_dataset": "global_crypto/minute_aggs_v1",
            "boundary_sample_ticker": sample_ticker,
            "oldest_flatfile_url": client.build_minute_aggs_url(start_date),
            "newest_flatfile_url": client.build_minute_aggs_url(end_date),
            "oldest_requested_url": client.build_minute_aggs_rest_url(sample_ticker, start_date),
            "newest_requested_url": client.build_minute_aggs_rest_url(sample_ticker, end_date),
        }

    def _day_is_complete(self, date_str: str, expected_tickers: list[str]) -> bool:
        raw_dir = self.settings.raw_dir / "massive" / date_str
        raw_present = any(raw_dir.glob(f"minute_aggs_{date_str}_*"))
        if not raw_present:
            return False
        if not self._parquet_day_present(date_str):
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
        range_chunks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        captured = [row for row in statuses if row.action == "captured"]
        skipped = [row for row in statuses if row.action == "skipped"]
        failed = [row for row in statuses if row.action == "failed"]
        chunk_rows = range_chunks or []
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
            "range_chunks": {
                "requested_count": len(chunk_rows),
                "captured_count": len(
                    [row for row in chunk_rows if row.get("status") == "captured"]
                ),
                "failed_count": len(
                    [row for row in chunk_rows if row.get("status") == "failed"]
                ),
                "chunk_days": self.settings.massive_rest_minute_aggs_range_chunk_days,
                "chunks": chunk_rows,
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

    def _attach_artifact_metadata(self, *, payload: dict[str, Any], artifact_dir: Path) -> None:
        """Keep range backfill returns compatible with training runtime wrappers."""
        payload["artifact_dir"] = str(artifact_dir)
        payload["artifact_paths"] = [
            str(artifact_dir / "config.json"),
            str(artifact_dir / "history_window.json"),
            str(artifact_dir / "capture_summary.json"),
            str(artifact_dir / "report.qmd"),
        ]

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
                metadata=trading_report_metadata(
                    report_kind="massive_minute_aggs_backfill",
                    run_id=batch_id,
                    owner_type=owner_type,
                    owner_key=owner_key,
                    instrument_scope=["SOL/USD", "BTC/USD", "ETH/USD"],
                    timeframe="1m",
                    summary_path="capture_summary.json",
                    config_path="config.json",
                ),
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
                            "- warehouse contract: raw `CSV.gz` + partitioned `Parquet` + normalized `SQL`",
                            f"- oldest requested day: `{payload['boundary_verification']['oldest_requested_day']}`",
                            f"- newest requested day: `{payload['boundary_verification']['newest_requested_day']}`",
                            f"- oldest flatfile url: `{payload['boundary_verification']['oldest_flatfile_url']}`",
                            f"- newest flatfile url: `{payload['boundary_verification']['newest_flatfile_url']}`",
                            f"- oldest rest url: `{payload['boundary_verification']['oldest_requested_url']}`",
                            f"- newest rest url: `{payload['boundary_verification']['newest_requested_url']}`",
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
