from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_orchestration_surface_exists() -> None:
    required = [
        REPO_ROOT / ".ai" / "README.md",
        REPO_ROOT / ".ai" / "swarm" / "swarm.yaml",
        REPO_ROOT / ".ai" / "swarm" / "lane_rules.yaml",
        REPO_ROOT / ".ai" / "swarm" / "promotion_ladder.yaml",
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
        "BACKTEST-001",
        "LABEL-001",
        "STRAT-001",
    } <= story_ids
    active_story_id = prd["activeStoryId"]
    if active_story_id:
        assert active_story_id in story_ids
        active_story = next(
            story for story in prd["userStories"] if story["id"] == active_story_id
        )
    else:
        assert prd["swarmState"] == "terminal_complete"
        assert prd["completionAuditState"] == "clean"
        active_story = None
    eligible_states = {"active", "ready", "recovery"}
    eligible_story_ids = {
        story["id"] for story in prd["userStories"] if story["state"] in eligible_states
    }
    if eligible_story_ids:
        assert active_story is not None
        assert active_story["passes"] is False
        assert active_story["state"] in eligible_states
    else:
        assert active_story is None or active_story["state"] not in eligible_states
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
    assert story_order.index("EXEC-001") < story_order.index("BACKTEST-001")
    assert story_order.index("BACKTEST-001") < story_order.index("LABEL-001")
    assert story_order.index("LABEL-001") < story_order.index("STRAT-001")
    by_id = {story["id"]: story for story in prd["userStories"]}
    assert by_id["ORCH-005"]["state"] == "done"
    assert by_id["BACKTEST-001"]["state"] == "deferred"
    assert by_id["LABEL-001"]["state"] == "deferred"
    assert by_id["STRAT-001"]["state"] == "deferred"


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


def test_machine_readable_swarm_policy_layer_is_present_and_consistent() -> None:
    swarm = yaml.safe_load((REPO_ROOT / ".ai" / "swarm" / "swarm.yaml").read_text())
    lane_rules = yaml.safe_load((REPO_ROOT / ".ai" / "swarm" / "lane_rules.yaml").read_text())
    promotion = yaml.safe_load((REPO_ROOT / ".ai" / "swarm" / "promotion_ladder.yaml").read_text())

    assert swarm["authority_mode"] == "policy-only"
    assert swarm["finder_policy"]["permanent_lanes_added"] is False
    assert "docs/project/current_runtime_truth.md" in swarm["packet"]["required_reads"]
    assert "docs/prd/crypto_backtesting_mission.md" in swarm["packet"]["required_reads"]
    assert "docs/policy/runtime_authority_and_promotion_ladder.md" in swarm["packet"]["required_reads"]

    lane_names = set(lane_rules["lanes"].keys())
    assert lane_names == {"research", "builder", "architecture", "writer_integrator"}
    assert lane_rules["common"]["writer_integrator_is_truth_owner"] is True
    assert lane_rules["lanes"]["builder"]["model_default"] == "ChatGPT 5.4"
    assert "research-finder" in lane_rules["lanes"]["research"]["modes"]
    assert "architecture-finder" in lane_rules["lanes"]["architecture"]["modes"]
    assert lane_rules["lanes"]["architecture"]["finder_rules"]["subtraction_first"] is True
    assert lane_rules["lanes"]["writer_integrator"]["authority"]["backlog_promotion_owner"] is True

    assert "execution_intent" in promotion["runtime_authority_chain"]
    assert promotion["promotion_rules"]["writer_integrator_is_only_promotion_authority"] is True
    assert "Chronos-2" in promotion["research_only_families"]
    assert "Monte Carlo" in promotion["research_only_families"]
    assert "autoresearch" in promotion["research_only_families"]


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


def test_sync_swarm_state_normalizes_writer_completion_audit_shape(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    scripts_dir = repo_root / "scripts" / "agents"
    state_dir = repo_root / ".ai" / "dropbox" / "state"
    scripts_dir.mkdir(parents=True)
    state_dir.mkdir(parents=True)

    for name in ("common.sh", "sync_swarm_state.sh"):
        shutil.copy2(REPO_ROOT / "scripts" / "agents" / name, scripts_dir / name)

    prd_path = repo_root / "prd.json"
    prd_path.write_text(
        json.dumps(
            {
                "project": "Defi-engine",
                "branchName": "main",
                "activeStoryId": "ORCH-005",
                "swarmState": "backlog_exhausted",
                "completionAuditState": "pending",
                "lastCompletionAuditReceiptId": "",
                "lastFinderAuditId": "",
                "userStories": [
                    {
                        "id": "ORCH-005",
                        "state": "done",
                        "passes": True,
                        "recovery_round": 0,
                        "origin": "promoted_gap",
                        "promoted_by": "completion_audit_architecture@2026-04-16T06:35:27-07:00",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    )

    (state_dir / "completion_audit_writer.json").write_text(
        json.dumps(
            {
                "status": "clean",
                "promoted_story_ids": [],
                "rationale": ["writer completion audit finished cleanly"],
                "audited_at": "2026-04-16T06:20:43-07:00",
            },
            indent=2,
        )
        + "\n"
    )

    subprocess.run(
        ["bash", str(scripts_dir / "sync_swarm_state.sh"), "--repo", str(repo_root)],
        check=True,
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    writer_audit = json.loads((state_dir / "completion_audit_writer.json").read_text())
    expected_audit_id = "completion_audit_writer::2026-04-16T06:20:43-07:00"
    assert writer_audit["audit_id"] == expected_audit_id
    assert writer_audit["deferred_story_ids"] == []

    prd = json.loads(prd_path.read_text())
    assert prd["lastCompletionAuditReceiptId"] == expected_audit_id
    assert prd["completionAuditState"] == "clean"
    assert prd["swarmState"] == "terminal_complete"


def test_repo_map_and_lane_guides_name_current_runtime_owners() -> None:
    repo_map = (REPO_ROOT / ".ai" / "index" / "current_repo_map.md").read_text()
    for surface in (
        "spot_chain_macro_v1",
        "global_regime_inputs_15m_v1",
        "global_regime_v1",
        "intraday_meta_stack_v1",
        "experiment_realized_feedback_v1",
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
