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
    assert "clear_stale_completion_trigger" in script
    assert "commit_accepted_story.sh" in script
    assert "performance_receipt" in script
    assert "periodic_completion_audit" in script


def test_supervisor_status_surfaces_monitoring_and_performance_fields() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "supervisor_status.sh").read_text()
    assert "supervisor_mode=" in script
    assert "last_terminal_audit=" in script
    assert "last_performance_receipt=" in script
    assert "last_auto_commit_receipt=" in script


def test_docs_sync_fields_are_exposed_in_health_and_status_surfaces() -> None:
    health_script = (REPO_ROOT / "scripts" / "agents" / "health_swarm.sh").read_text()
    status_script = (REPO_ROOT / "scripts" / "agents" / "status_swarm.sh").read_text()
    relaunch_script = (REPO_ROOT / "scripts" / "agents" / "relaunch_stale_lanes.sh").read_text()

    assert "docsSyncState" in health_script
    assert "docsTruthReceiptId" in health_script
    assert "docs_truth_receipt" in health_script
    assert "storyPromotionReceiptId" in health_script
    assert "researchProposalReviewReceiptId" in health_script
    assert "docs_sync_state=" in status_script
    assert "docs_truth_receipt=" in status_script
    assert "story_promotion_receipt=" in status_script
    assert "research_proposal_review_receipt=" in status_script
    assert 'if [[ "$builder_status" == "completed" ]]; then' in relaunch_script


def test_run_persistent_cycle_waits_for_inflight_finder_lanes_before_relaunching() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh").read_text()
    assert 'if [[ "$(lane_status architecture)" == "running" ]]; then' in script
    assert 'if [[ "$(lane_status research)" == "running" ]]; then' in script
    assert 'if [[ "$(lane_status writer-integrator)" == "running" ]]; then' in script
    assert "waiting on writer finder output" in script


def test_run_persistent_cycle_defers_story_activation_to_sync_swarm_state() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh").read_text()

    assert "ensure_active_story()" not in script
    assert 'update_story_state.sh" --repo "$repo_root" --story-id "$next_story" --state active' not in script
    assert 'update_story_state.sh" --repo "$repo_root" --story-id "$active_story" --state active' not in script
    assert "sync_swarm_state()" in script
    assert 'status_swarm.sh" --repo "$repo_root" --session "$session_name" >/dev/null' not in script


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


def test_sync_swarm_state_reactivates_best_deferred_followon_from_completion_audit(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts" / "agents"
    state_dir = repo_root / ".ai" / "dropbox" / "state"
    scripts_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    (repo_root / "scripts").mkdir(exist_ok=True)
    for name in ("common.sh", "sync_swarm_state.sh"):
        shutil.copy2(REPO_ROOT / "scripts" / "agents" / name, scripts_dir / name)

    (state_dir / "finder_state.json").write_text(
        json.dumps(
            {
                "pendingTrigger": {
                    "triggerId": "completion_audit::receipt-1",
                    "triggerType": "completion_audit",
                    "scope": "completion_audit",
                    "storyId": "",
                },
                "queuedReceiptFollowons": [],
                "lastProcessedReceiptId": "",
                "lastProcessedFailureSignature": "",
                "lastProcessedCompletionScope": "",
                "lastProcessedPerformanceReceiptId": "",
                "lastTerminalAuditAt": "",
                "lastFinderAuditId": "completion_audit_writer::2026-04-16T09:01:50-07:00",
                "lastWriterDecisionId": "completion_audit_writer::2026-04-16T09:01:50-07:00",
            },
            indent=2,
        )
        + "\n"
    )
    (state_dir / "lane_health.json").write_text(json.dumps({"lanes": [], "story": {}}, indent=2) + "\n")
    (state_dir / "completion_audit_writer.json").write_text(
        json.dumps(
            {
                "audit_id": "completion_audit_writer::2026-04-16T09:01:50-07:00",
                "status": "audit_known_only",
                "promoted_story_ids": [],
                "deferred_story_ids": ["EXEC-001", "BACKTEST-001"],
                "rationale": ["reactivate the best current deferred follow-on"],
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
                "activeStoryId": "",
                "swarmState": "audit_followons_present",
                "completionAuditState": "pending",
                "lastCompletionAuditReceiptId": "",
                "lastFinderAuditId": "",
                "userStories": [
                    {"id": "ORCH-006", "state": "done", "passes": True, "priority": 10},
                    {"id": "EXEC-001", "state": "deferred", "passes": False, "priority": 11},
                    {"id": "BACKTEST-001", "state": "deferred", "passes": False, "priority": 12},
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
    finder_state = json.loads((state_dir / "finder_state.json").read_text())
    assert doc["activeStoryId"] == "EXEC-001"
    assert doc["swarmState"] == "active"
    assert doc["completionAuditState"] == "pending"
    story = next(row for row in doc["userStories"] if row["id"] == "EXEC-001")
    assert story["state"] == "active"
    assert finder_state["pendingTrigger"] is None


def test_run_persistent_cycle_waits_for_scoped_completion_audit_workers_before_relaunching() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh").read_text()

    assert "lane_has_active_scope_mode()" in script
    assert "lane_has_active_scope_mode architecture completion_audit completion_audit" in script
    assert 'lane_has_active_scope_mode writer-integrator completion_audit completion_audit' in script
    assert "waiting on completion audit lane output" in script


def test_status_swarm_is_read_only_unless_refresh_is_requested() -> None:
    script = (REPO_ROOT / "scripts" / "agents" / "status_swarm.sh").read_text()

    assert "--refresh" in script
    assert 'if [[ "$refresh" == "true" ]]; then' in script
    assert '"$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --no-mail --quiet >/dev/null' in script
