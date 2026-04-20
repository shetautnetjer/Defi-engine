from __future__ import annotations

import asyncio
import json

from d5_trading_engine.capture.massive_backfill import MassiveMinuteAggsBackfill
from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.storage.truth.engine import run_migrations_to_head
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import ArtifactReference


def test_massive_backfill_range_writes_artifacts(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    runner = CaptureRunner(settings)
    backfill = MassiveMinuteAggsBackfill(settings, runner=runner)

    async def _fake_capture(self, start_date: str, end_date: str, **kwargs) -> dict:
        assert kwargs["allowed_tickers"] == settings.massive_default_tickers
        return {
            "run_id": f"run_{start_date}_{end_date}",
            "captured_dates": ["2026-04-14", "2026-04-15"],
            "row_count": 2,
        }

    def _noop_receipts(self, run_id: str, *, context=None):
        assert run_id.startswith("run_")
        assert context is not None
        return None

    monkeypatch.setattr(CaptureRunner, "capture_massive_minute_aggs_range", _fake_capture)
    monkeypatch.setattr(CaptureRunner, "write_capture_receipts", _noop_receipts)

    payload = asyncio.run(
        backfill.backfill_range(
            start_date="2026-04-14",
            end_date="2026-04-15",
            resume=True,
        )
    )

    assert payload["status"] == "success"
    assert payload["days"]["captured_count"] == 2
    assert payload["days"]["skipped_count"] == 0

    artifact_dir = settings.data_dir / "research" / "massive_minute_aggs" / payload["batch_id"]
    assert payload["artifact_dir"] == str(artifact_dir)
    assert str(artifact_dir / "capture_summary.json") in payload["artifact_paths"]
    summary = json.loads((artifact_dir / "capture_summary.json").read_text(encoding="utf-8"))
    history_window = json.loads((artifact_dir / "history_window.json").read_text(encoding="utf-8"))
    assert summary["batch_id"] == payload["batch_id"]
    assert history_window["resolved_start_date"] == "2026-04-14"
    assert history_window["resolved_end_date"] == "2026-04-15"

    session = get_session(settings)
    try:
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="capture_batch", owner_key=payload["batch_id"])
            .all()
        )
    finally:
        session.close()

    assert {artifact.artifact_type for artifact in artifacts} == {
        "massive_minute_aggs_backfill_config",
        "massive_minute_aggs_history_window",
        "massive_minute_aggs_backfill_summary",
        "massive_minute_aggs_backfill_report_qmd",
    }


def test_massive_backfill_range_uses_multi_day_rest_chunks(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    settings.massive_rest_minute_aggs_range_chunk_days = 30
    runner = CaptureRunner(settings)
    backfill = MassiveMinuteAggsBackfill(settings, runner=runner)

    observed_ranges: list[tuple[str, str]] = []

    async def _fake_range_capture(self, start_date: str, end_date: str, **kwargs) -> dict:
        assert kwargs["allowed_tickers"] == settings.massive_default_tickers
        observed_ranges.append((start_date, end_date))
        return {
            "run_id": f"range_{start_date}_{end_date}",
            "captured_dates": [
                row.date
                for row in backfill._iter_missing_windows(start_date=start_date, end_date=end_date)
            ],
            "row_count": 1,
        }

    def _noop_receipts(self, run_id: str, *, context=None):
        assert run_id.startswith("range_")
        assert context is not None
        return None

    monkeypatch.setattr(CaptureRunner, "capture_massive_minute_aggs_range", _fake_range_capture)
    monkeypatch.setattr(CaptureRunner, "write_capture_receipts", _noop_receipts)
    monkeypatch.setattr(MassiveMinuteAggsBackfill, "_day_is_complete", lambda self, date_str, tickers: False)

    payload = asyncio.run(
        backfill.backfill_range(
            start_date="2026-01-01",
            end_date="2026-03-05",
            resume=True,
        )
    )

    assert observed_ranges == [
        ("2026-01-01", "2026-01-30"),
        ("2026-01-31", "2026-03-01"),
        ("2026-03-02", "2026-03-05"),
    ]
    assert payload["days"]["captured_count"] == 64
    assert payload["range_chunks"]["requested_count"] == 3


def test_massive_historical_cache_status_reports_next_missing_day(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    backfill = MassiveMinuteAggsBackfill(settings, runner=CaptureRunner(settings))

    monkeypatch.setattr(
        MassiveMinuteAggsBackfill,
        "resolve_full_free_tier_window",
        lambda self: ("2026-04-14", "2026-04-16"),
    )

    complete_days = {"2026-04-14", "2026-04-16"}
    monkeypatch.setattr(
        MassiveMinuteAggsBackfill,
        "_raw_day_present",
        lambda self, date_str: date_str in complete_days,
    )
    monkeypatch.setattr(
        MassiveMinuteAggsBackfill,
        "_parquet_day_present",
        lambda self, date_str: date_str in complete_days,
    )
    monkeypatch.setattr(
        MassiveMinuteAggsBackfill,
        "_normalized_tickers_by_date",
        lambda self, **kwargs: {
            day: {ticker.upper() for ticker in settings.massive_default_tickers}
            for day in complete_days
        },
    )

    status = backfill.historical_cache_status()

    assert status["resolved_start_date"] == "2026-04-14"
    assert status["resolved_end_date"] == "2026-04-16"
    assert status["requested_day_count"] == 3
    assert status["completed_day_count"] == 2
    assert status["parquet_complete_day_count"] == 2
    assert status["missing_day_count"] == 1
    assert status["complete"] is False
    assert status["earliest_completed_date"] == "2026-04-14"
    assert status["latest_completed_date"] == "2026-04-16"
    assert status["next_missing_date"] == "2026-04-15"


def test_massive_backfill_missing_full_free_tier_bounds_to_max_days(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    backfill = MassiveMinuteAggsBackfill(settings, runner=CaptureRunner(settings))

    monkeypatch.setattr(
        MassiveMinuteAggsBackfill,
        "historical_cache_status",
        lambda self: {
            "entitlement_assumption": "massive_free_tier_crypto_minute_2y",
            "resolved_start_date": "2026-04-10",
            "resolved_end_date": "2026-04-20",
            "default_tickers": list(settings.massive_default_tickers),
            "expected_ticker_count": len(settings.massive_default_tickers),
            "requested_day_count": 11,
            "completed_day_count": 2,
            "missing_day_count": 9,
            "complete": False,
            "earliest_completed_date": "2026-04-10",
            "latest_completed_date": "2026-04-11",
            "next_missing_date": "2026-04-12",
            "generated_at": "2026-04-18T00:00:00+00:00",
        },
    )

    observed: dict[str, str] = {}

    async def _fake_backfill_range(self, *, start_date: str, end_date: str, resume: bool, mode: str):
        observed["start_date"] = start_date
        observed["end_date"] = end_date
        observed["mode"] = mode
        observed["resume"] = str(resume)
        return {
            "status": "success",
            "batch_id": "capture_batch_massive_minute_aggs_test",
            "mode": mode,
            "resume": resume,
            "resolved_start_date": start_date,
            "resolved_end_date": end_date,
            "days": {
                "requested_count": 2,
                "captured_count": 2,
                "skipped_count": 0,
                "failed_count": 0,
            },
        }

    monkeypatch.setattr(MassiveMinuteAggsBackfill, "backfill_range", _fake_backfill_range)

    payload = asyncio.run(backfill.backfill_missing_full_free_tier(max_days=2, resume=True))

    assert observed == {
        "start_date": "2026-04-12",
        "end_date": "2026-04-13",
        "mode": "incremental_missing",
        "resume": "True",
    }
    assert payload["resolved_start_date"] == "2026-04-12"
    assert payload["resolved_end_date"] == "2026-04-13"


def test_massive_historical_cache_status_reports_next_missing_day(settings, monkeypatch) -> None:
    backfill = MassiveMinuteAggsBackfill(settings, runner=CaptureRunner(settings))
    monkeypatch.setattr(
        backfill,
        "resolve_full_free_tier_window",
        lambda: ("2026-04-14", "2026-04-16"),
    )

    completed = {"2026-04-14", "2026-04-15"}
    monkeypatch.setattr(
        backfill,
        "_raw_day_present",
        lambda date_str: date_str in completed,
    )
    monkeypatch.setattr(
        backfill,
        "_parquet_day_present",
        lambda date_str: date_str in completed,
    )
    monkeypatch.setattr(
        backfill,
        "_normalized_tickers_by_date",
        lambda **kwargs: {
            day: {ticker.upper() for ticker in settings.massive_default_tickers}
            for day in completed
        },
    )

    status = backfill.historical_cache_status()

    assert status["complete"] is False
    assert status["completed_day_count"] == 2
    assert status["parquet_complete_day_count"] == 2
    assert status["missing_day_count"] == 1
    assert status["next_missing_date"] == "2026-04-16"
    assert status["latest_completed_date"] == "2026-04-15"


def test_massive_backfill_missing_full_free_tier_bounds_to_max_days(settings, monkeypatch) -> None:
    backfill = MassiveMinuteAggsBackfill(settings, runner=CaptureRunner(settings))
    monkeypatch.setattr(
        backfill,
        "historical_cache_status",
        lambda: {
            "entitlement_assumption": "massive_free_tier_crypto_minute_2y",
            "complete": False,
            "resolved_start_date": "2026-04-14",
            "resolved_end_date": "2026-04-20",
            "default_tickers": list(settings.massive_default_tickers),
            "expected_ticker_count": len(settings.massive_default_tickers),
            "requested_day_count": 7,
            "completed_day_count": 2,
            "missing_day_count": 5,
            "next_missing_date": "2026-04-16",
            "earliest_completed_date": "2026-04-14",
            "latest_completed_date": "2026-04-15",
            "generated_at": "2026-04-18T00:00:00+00:00",
        },
    )

    captured: dict[str, object] = {}

    async def _fake_backfill_range(*, start_date: str, end_date: str, resume: bool = True, mode: str = "range"):
        captured.update(
            {
                "start_date": start_date,
                "end_date": end_date,
                "resume": resume,
                "mode": mode,
            }
        )
        return {
            "status": "success",
            "batch_id": "capture_batch_test",
            "mode": mode,
            "resume": resume,
            "resolved_start_date": start_date,
            "resolved_end_date": end_date,
            "days": {"requested_count": 2, "captured_count": 2, "skipped_count": 0, "failed_count": 0},
        }

    monkeypatch.setattr(backfill, "backfill_range", _fake_backfill_range)

    payload = asyncio.run(backfill.backfill_missing_full_free_tier(max_days=2, resume=True))

    assert payload["status"] == "success"
    assert captured == {
        "start_date": "2026-04-16",
        "end_date": "2026-04-17",
        "resume": True,
        "mode": "incremental_missing",
    }
