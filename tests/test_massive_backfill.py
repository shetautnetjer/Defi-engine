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

    async def _fake_capture(self, date_str: str, **kwargs) -> str:
        assert kwargs["allowed_tickers"] == settings.massive_default_tickers
        assert kwargs["partition"] == date_str
        return f"run_{date_str}"

    def _noop_receipts(self, run_id: str, *, context=None):
        assert run_id.startswith("run_")
        assert context is not None
        return None

    monkeypatch.setattr(CaptureRunner, "capture_massive_minute_aggs", _fake_capture)
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
