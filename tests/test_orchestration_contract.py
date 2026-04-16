from __future__ import annotations

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_orchestration_surface_exists() -> None:
    required = [
        REPO_ROOT / ".ai" / "README.md",
        REPO_ROOT / ".ai" / "agents" / "common.md",
        REPO_ROOT / ".ai" / "agents" / "research.md",
        REPO_ROOT / ".ai" / "agents" / "builder.md",
        REPO_ROOT / ".ai" / "agents" / "architecture.md",
        REPO_ROOT / ".ai" / "agents" / "writer_integrator.md",
        REPO_ROOT / ".ai" / "index" / "current_repo_map.md",
        REPO_ROOT / ".ai" / "templates" / "research.md",
        REPO_ROOT / ".ai" / "templates" / "builder.md",
        REPO_ROOT / ".ai" / "templates" / "architecture.md",
        REPO_ROOT / ".ai" / "templates" / "writer_integrator.md",
        REPO_ROOT / ".ai" / "templates" / "architecture_finder.md",
        REPO_ROOT / ".ai" / "templates" / "research_finder.md",
        REPO_ROOT / ".ai" / "templates" / "architecture_completion_audit.md",
        REPO_ROOT / ".ai" / "templates" / "writer_completion_audit.md",
        REPO_ROOT / ".ai" / "dropbox" / "README.md",
        REPO_ROOT / ".ai" / "dropbox" / "state" / "accepted_receipts" / ".gitkeep",
        REPO_ROOT / "prd.json",
        REPO_ROOT / "progress.txt",
        REPO_ROOT / "scripts" / "agents" / "start_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "start_supervisor.sh",
        REPO_ROOT / "scripts" / "agents" / "supervisor_status.sh",
        REPO_ROOT / "scripts" / "agents" / "status_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "refresh_watch_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "health_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "relaunch_stale_lanes.sh",
        REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh",
        REPO_ROOT / "scripts" / "agents" / "sync_swarm_state.sh",
        REPO_ROOT / "scripts" / "agents" / "write_acceptance_receipt.sh",
        REPO_ROOT / "scripts" / "agents" / "update_story_state.sh",
        REPO_ROOT / "scripts" / "agents" / "promote_gap_story.sh",
        REPO_ROOT / "scripts" / "agents" / "send_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "capture_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "stop_supervisor.sh",
        REPO_ROOT / "scripts" / "agents" / "stop_swarm.sh",
        REPO_ROOT / "scripts" / "ralph" / "ralph.sh",
        REPO_ROOT / "scripts" / "ralph" / "CODEX.md",
        REPO_ROOT / "docs" / "runbooks" / "ralph_tmux_swarm.md",
    ]
    missing = [path for path in required if not path.exists()]
    assert not missing


def test_prd_has_active_story_and_runtime_owner_backlog() -> None:
    prd = json.loads((REPO_ROOT / "prd.json").read_text())
    assert prd["project"] == "Defi-engine"
    assert prd["branchName"] == "main"
    assert prd["swarmState"] in {
        "active",
        "blocked",
        "backlog_exhausted",
        "audit_followons_present",
        "terminal_complete",
    }
    assert prd["completionAuditState"] in {"pending", "running", "clean", "gaps_promoted"}
    assert "lastCompletionAuditReceiptId" in prd
    assert "lastFinderAuditId" in prd
    story_ids = {story["id"] for story in prd["userStories"]}
    assert {
        "POL-001",
        "RISK-001",
        "SETTLE-001",
        "ORCH-005",
        "SOURCE-001",
        "RESEARCH-001",
        "EXEC-001",
    } <= story_ids
    assert prd["activeStoryId"] in story_ids
    active_story = next(
        story for story in prd["userStories"] if story["id"] == prd["activeStoryId"]
    )
    eligible_states = {"active", "ready", "recovery"}
    eligible_story_ids = {
        story["id"] for story in prd["userStories"] if story["state"] in eligible_states
    }
    if eligible_story_ids:
        assert active_story["passes"] is False
        assert active_story["state"] in eligible_states
    else:
        assert active_story["state"] not in eligible_states
    for story in prd["userStories"]:
        assert story["state"] in {
            "ready",
            "active",
            "recovery",
            "blocked_external",
            "deferred",
            "done",
            "escalated",
        }
        assert "recovery_round" in story
        assert "origin" in story
        assert "promoted_by" in story

    story_order = [story["id"] for story in prd["userStories"]]
    assert story_order.index("ORCH-005") < story_order.index("SOURCE-001")
    assert story_order.index("SOURCE-001") < story_order.index("RESEARCH-001")
    assert story_order.index("RESEARCH-001") < story_order.index("EXEC-001")
    by_id = {story["id"]: story for story in prd["userStories"]}
    assert by_id["ORCH-005"]["state"] == "active"
    assert by_id["SOURCE-001"]["state"] == "ready"
    assert by_id["RESEARCH-001"]["state"] == "ready"
    assert by_id["EXEC-001"]["state"] == "deferred"


def test_scripts_are_executable_and_prompts_reference_lane_guides() -> None:
    scripts = [
        REPO_ROOT / "scripts" / "agents" / "start_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "start_supervisor.sh",
        REPO_ROOT / "scripts" / "agents" / "supervisor_status.sh",
        REPO_ROOT / "scripts" / "agents" / "status_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "refresh_watch_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "health_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "relaunch_stale_lanes.sh",
        REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh",
        REPO_ROOT / "scripts" / "agents" / "sync_swarm_state.sh",
        REPO_ROOT / "scripts" / "agents" / "write_acceptance_receipt.sh",
        REPO_ROOT / "scripts" / "agents" / "update_story_state.sh",
        REPO_ROOT / "scripts" / "agents" / "promote_gap_story.sh",
        REPO_ROOT / "scripts" / "agents" / "send_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "capture_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "stop_supervisor.sh",
        REPO_ROOT / "scripts" / "agents" / "stop_swarm.sh",
        REPO_ROOT / "scripts" / "ralph" / "ralph.sh",
    ]
    for path in scripts:
        assert os.access(path, os.X_OK), f"{path} is not executable"

    prompt_paths = [
        REPO_ROOT / ".ai" / "templates" / "research.md",
        REPO_ROOT / ".ai" / "templates" / "builder.md",
        REPO_ROOT / ".ai" / "templates" / "architecture.md",
        REPO_ROOT / ".ai" / "templates" / "writer_integrator.md",
        REPO_ROOT / ".ai" / "templates" / "architecture_finder.md",
        REPO_ROOT / ".ai" / "templates" / "research_finder.md",
        REPO_ROOT / ".ai" / "templates" / "architecture_completion_audit.md",
        REPO_ROOT / ".ai" / "templates" / "writer_completion_audit.md",
        REPO_ROOT / "scripts" / "ralph" / "CODEX.md",
    ]
    for path in prompt_paths:
        contents = path.read_text()
        assert ".ai/agents/common.md" in contents

    writer_prompt = (REPO_ROOT / ".ai" / "templates" / "writer_integrator.md").read_text()
    assert "lane_health.md" in writer_prompt
    assert "mailbox.jsonl" in writer_prompt
    assert "finder_state.json" in writer_prompt
    assert "finder_decision.json" in writer_prompt
    assert "write_acceptance_receipt.sh" in writer_prompt
    assert "update_story_state.sh" in writer_prompt

    research_prompt = (REPO_ROOT / ".ai" / "templates" / "research.md").read_text()
    assert "inspect repo-local docs, contracts, and existing code first" in research_prompt
    assert "do not widen into" in research_prompt

    architecture_finder_prompt = (
        REPO_ROOT / ".ai" / "templates" / "architecture_finder.md"
    ).read_text()
    research_finder_prompt = (REPO_ROOT / ".ai" / "templates" / "research_finder.md").read_text()
    assert "subtraction" in architecture_finder_prompt
    assert "finder_state.json" in architecture_finder_prompt
    assert "evidence-backed" in research_finder_prompt
    assert "finder_state.json" in research_finder_prompt


def test_continuous_loop_uses_story_activation_and_story_scoped_writer_receipts() -> None:
    persistent_cycle = (REPO_ROOT / "scripts" / "agents" / "run_persistent_cycle.sh").read_text()
    assert "ensure_active_story()" in persistent_cycle
    assert "--state active" in persistent_cycle
    assert "queue_completion_trigger" in persistent_cycle
    assert "finder_phase" in persistent_cycle
    assert "clear_processed_finder" in persistent_cycle

    health_swarm = (REPO_ROOT / "scripts" / "agents" / "health_swarm.sh").read_text()
    assert "lane process is still alive for the current story" in health_swarm
    assert "storyScopedOutputPath" in health_swarm
    assert "\"acceptance receipt\"" in health_swarm

    sync_swarm_state = (REPO_ROOT / "scripts" / "agents" / "sync_swarm_state.sh").read_text()
    assert '"swarmState"' in sync_swarm_state
    assert '"completionAuditState"' in sync_swarm_state


def test_repo_map_and_lane_guides_name_current_runtime_owners() -> None:
    repo_map = (REPO_ROOT / ".ai" / "index" / "current_repo_map.md").read_text()
    for surface in (
        "spot_chain_macro_v1",
        "global_regime_inputs_15m_v1",
        "global_regime_v1",
        "intraday_meta_stack_v1",
        "Policy",
        "risk/",
        "settlement/",
    ):
        assert surface in repo_map

    architecture_guide = (REPO_ROOT / ".ai" / "agents" / "architecture.md").read_text()
    builder_guide = (REPO_ROOT / ".ai" / "agents" / "builder.md").read_text()
    assert "jetbrains-skill" in architecture_guide
    assert "jetbrains-mcp" in architecture_guide
    assert "jetbrains-mcp" in builder_guide
