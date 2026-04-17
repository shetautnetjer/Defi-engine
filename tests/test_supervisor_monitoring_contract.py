from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_run_persistent_cycle_keeps_terminal_monitoring_and_receipt_backed_hooks() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh").read_text()
    assert 'supervisor_mode="terminal_monitoring"' in script
    assert "sync_performance_receipts.sh" in script
    assert "queue_performance_trigger" in script
    assert "queue_periodic_terminal_audit" in script
    assert "commit_accepted_story.sh" in script
    assert "performance_receipt" in script
    assert "periodic_completion_audit" in script


def test_supervisor_status_surfaces_monitoring_and_performance_fields() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "supervisor_status.sh").read_text()
    assert "supervisor_mode=" in script
    assert "last_terminal_audit=" in script
    assert "last_performance_receipt=" in script
    assert "last_auto_commit_receipt=" in script


def test_sync_swarm_state_clears_active_story_when_terminal_complete(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts" / "agents"
    state_dir = repo_root / ".ai" / "dropbox" / "state"
    scripts_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    for name in ("common.sh", "sync_swarm_state.sh"):
        shutil.copy2(REPO_ROOT / "scripts" / "agents" / name, scripts_dir / name)

    (state_dir / "finder_state.json").write_text(
        json.dumps(
            {
                "pendingTrigger": None,
                "queuedReceiptFollowons": [],
                "lastProcessedReceiptId": "",
                "lastProcessedFailureSignature": "",
                "lastProcessedCompletionScope": "",
                "lastProcessedPerformanceReceiptId": "",
                "lastTerminalAuditAt": "",
                "lastFinderAuditId": "",
                "lastWriterDecisionId": "",
            },
            indent=2,
        )
        + "\n"
    )
    (state_dir / "lane_health.json").write_text(
        json.dumps({"lanes": []}, indent=2) + "\n"
    )
    (state_dir / "completion_audit_writer.json").write_text(
        json.dumps(
            {
                "audit_id": "completion_audit_writer::2026-04-16T09:01:50-07:00",
                "status": "clean",
                "promoted_story_ids": [],
                "deferred_story_ids": [],
                "rationale": ["clean"],
                "audited_at": "2026-04-16T09:01:50-07:00",
            },
            indent=2,
        )
        + "\n"
    )
    (repo_root / "prd.json").write_text(
        json.dumps(
            {
                "project": "Defi-engine",
                "activeStoryId": "RESEARCH-001",
                "swarmState": "backlog_exhausted",
                "completionAuditState": "pending",
                "lastCompletionAuditReceiptId": "",
                "lastFinderAuditId": "",
                "userStories": [
                    {"id": "RESEARCH-001", "state": "done", "passes": True},
                    {"id": "EXEC-001", "state": "deferred", "passes": False},
                ],
            },
            indent=2,
        )
        + "\n"
    )

    subprocess.run(
        ["bash", str(scripts_dir / "sync_swarm_state.sh"), "--repo", str(repo_root)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    doc = json.loads((repo_root / "prd.json").read_text())
    assert doc["swarmState"] == "terminal_complete"
    assert doc["completionAuditState"] == "clean"
    assert doc["activeStoryId"] == ""
