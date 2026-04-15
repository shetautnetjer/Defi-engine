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
        REPO_ROOT / ".ai" / "dropbox" / "README.md",
        REPO_ROOT / "prd.json",
        REPO_ROOT / "progress.txt",
        REPO_ROOT / "scripts" / "agents" / "start_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "status_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "send_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "capture_swarm.sh",
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
    assert prd["activeStoryId"] == "POL-001"
    story_ids = {story["id"] for story in prd["userStories"]}
    assert {"POL-001", "RISK-001", "SETTLE-001"} <= story_ids
    active_story = next(story for story in prd["userStories"] if story["id"] == prd["activeStoryId"])
    assert active_story["passes"] is False


def test_scripts_are_executable_and_prompts_reference_lane_guides() -> None:
    scripts = [
        REPO_ROOT / "scripts" / "agents" / "start_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "status_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "send_swarm.sh",
        REPO_ROOT / "scripts" / "agents" / "capture_swarm.sh",
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
        REPO_ROOT / "scripts" / "ralph" / "CODEX.md",
    ]
    for path in prompt_paths:
        contents = path.read_text()
        assert ".ai/agents/common.md" in contents


def test_repo_map_and_lane_guides_name_current_runtime_owners() -> None:
    repo_map = (REPO_ROOT / ".ai" / "index" / "current_repo_map.md").read_text()
    for surface in (
        "spot_chain_macro_v1",
        "global_regime_inputs_15m_v1",
        "global_regime_v1",
        "intraday_meta_stack_v1",
        "policy/",
        "risk/",
        "settlement/",
    ):
        assert surface in repo_map

    architecture_guide = (REPO_ROOT / ".ai" / "agents" / "architecture.md").read_text()
    builder_guide = (REPO_ROOT / ".ai" / "agents" / "builder.md").read_text()
    assert "jetbrains-skill" in architecture_guide
    assert "jetbrains-mcp" in architecture_guide
    assert "jetbrains-mcp" in builder_guide
