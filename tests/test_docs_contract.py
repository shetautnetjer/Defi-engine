from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "project" / "bootstrap_inventory.md",
    REPO_ROOT / "docs" / "task" / "source_expansion_preconditions.md",
    REPO_ROOT / "docs" / "plans" / "source_expansion_preconditions.md",
    REPO_ROOT / "docs" / "plans" / "historical_research_protocol.md",
    REPO_ROOT / "docs" / "task" / "bootstrap_truth_sync.md",
    REPO_ROOT / "docs" / "architecture" / "bootstrap_architecture.md",
    REPO_ROOT / "docs" / "runbooks" / "first_capture.md",
    REPO_ROOT / "docs" / "runbooks" / "feature_condition_shadow_cycle.md",
    REPO_ROOT / "docs" / "runbooks" / "ralph_tmux_swarm.md",
    REPO_ROOT / "docs" / "math" / "regime_shadow_modeling_contracts.md",
    REPO_ROOT / "docs" / "test" / "bootstrap_validation.md",
]
REQUIRED_DOCS = ACTIVE_DOCS + [
    REPO_ROOT / "docs" / "gaps" / "bootstrap_gap_register.md",
    REPO_ROOT / "docs" / "handoff" / "2026-04-12_bootstrap_phase_1.md",
]


def test_single_root_env_template_exists() -> None:
    assert (REPO_ROOT / ".env.example").exists()
    assert not (REPO_ROOT / "env.example").exists()


def test_required_bootstrap_docs_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not path.exists()]
    assert not missing


def test_active_docs_do_not_reference_stale_cli_strings() -> None:
    stale_strings = [
        "d5 init-db",
        "Base.metadata.create_all()",
        "create the current SQLite schema from ORM metadata",
        "there is no `tests/` directory yet",
    ]

    for path in ACTIVE_DOCS:
        contents = path.read_text()
        for stale in stale_strings:
            assert stale not in contents, f"found stale text {stale!r} in {path}"


def test_ralph_runbook_mentions_persistent_supervision() -> None:
    runbook = (REPO_ROOT / "docs" / "runbooks" / "ralph_tmux_swarm.md").read_text()
    assert "start_supervisor.sh" in runbook
    assert "supervisor_status.sh" in runbook
    assert "health_swarm.sh" in runbook
    assert "refresh_watch_swarm.sh" in runbook
    assert "relaunch_stale_lanes.sh" in runbook
    assert "run_persistent_cycle.sh" in runbook
    assert "mailbox.jsonl" in runbook
    assert "stops both the detached supervisor and the tmux session" in runbook
    assert "session control only" in runbook
    assert "lane-health" in runbook
    assert "accepted_receipts" in runbook
    assert "detached supervisor state" in runbook
    assert "alive" in runbook
    assert "producing" in runbook
    assert "accepted" in runbook
    assert "mailbox_current.json" in runbook
    assert "finder_state.json" in runbook
    assert "finder_decision.json" in runbook
    assert "architecture-finder" in runbook
    assert "research-finder" in runbook
    assert "swarmState" in runbook
    assert "completionAuditState" in runbook
    assert "terminal_complete" in runbook
    assert "audit_followons_present" in runbook
