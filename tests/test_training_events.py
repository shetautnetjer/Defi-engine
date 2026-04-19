from __future__ import annotations

import json
from pathlib import Path
import subprocess

import orjson

from d5_trading_engine.research_loop.training_events import append_training_event

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "training" / "bin" / "emit_training_event.py"


def test_append_training_event_writes_thin_envelope(settings) -> None:
    queue_path = settings.repo_root / "training" / "automation" / "state" / "events.jsonl"
    event = append_training_event(
        settings,
        event_type="paper_session_closed",
        summary="Closed a paper session and wrote a reviewable report.",
        owner_kind="paper_session",
        run_id="paper_session_fixture",
        qmd_reports=[Path("docs/reports/paper_session_fixture.qmd")],
        sql_refs=["paper_session:paper_session_fixture"],
        context_files=[Path("src/d5_trading_engine/paper_runtime/operator.py")],
        notes="Keep, revert, or shadow one bounded paper-profile change.",
    )

    written = orjson.loads(queue_path.read_bytes().splitlines()[0])
    assert written["event_id"] == event["event_id"]
    assert written["event_type"] == "paper_session_closed"
    assert written["repo_root"] == str(settings.repo_root)
    assert written["summary"] == "Closed a paper session and wrote a reviewable report."
    assert written["qmd_reports"] == ["docs/reports/paper_session_fixture.qmd"]
    assert written["sql_refs"] == ["paper_session:paper_session_fixture"]
    assert written["context_files"] == ["src/d5_trading_engine/paper_runtime/operator.py"]
    assert "payload" not in written


def test_emit_training_event_script_flattens_payload_fields(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True)
    payload_path = repo_root / "payload.json"
    payload_path.write_text(
        json.dumps(
            {
                "summary": "Feature materialization finished.",
                "run_id": "feature_run_fixture",
                "qmd_reports": ["docs/reports/feature_run_fixture.qmd"],
                "sql_refs": ["feature_run:feature_run_fixture"],
                "context_files": ["src/d5_trading_engine/features/materializer.py"],
                "notes": "Review one bounded feature change.",
            }
        ),
        encoding="utf-8",
    )
    queue_path = repo_root / "training" / "automation" / "state" / "events.jsonl"

    result = subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--event-type",
            "feature_run_completed",
            "--repo-root",
            str(repo_root),
            "--queue",
            str(queue_path),
            "--payload-path",
            str(payload_path),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    emitted = json.loads(result.stdout)
    written = orjson.loads(queue_path.read_bytes().splitlines()[0])
    assert emitted["event_type"] == "feature_run_completed"
    assert emitted["repo_root"] == str(repo_root.resolve())
    assert emitted["qmd_reports"] == ["docs/reports/feature_run_fixture.qmd"]
    assert emitted["sql_refs"] == ["feature_run:feature_run_fixture"]
    assert emitted["context_files"] == ["src/d5_trading_engine/features/materializer.py"]
    assert emitted["summary"] == "Feature materialization finished."
    assert written == emitted
    assert "payload" not in emitted
