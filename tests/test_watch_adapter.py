from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_watch_module():
    module_name = "codex_watch_adapter_under_test"
    script_path = REPO_ROOT / "scripts" / "agents" / "codex_watch_adapter.py"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def seed_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    for rel_path in (
        ".ai/swarm/watcher.yaml",
        ".ai/templates/watcher.md",
        ".ai/dropbox/README.md",
    ):
        source = REPO_ROOT / rel_path
        target = repo_root / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    write_json(
        repo_root / "prd.json",
        {
            "activeStoryId": "LABEL-001",
            "userStories": [
                {"id": "LABEL-001", "state": "active"},
                {"id": "STRAT-001", "state": "deferred"},
                {"id": "ORCH-005", "state": "done"},
            ],
        },
    )
    (repo_root / ".ai" / "dropbox" / "state" / "accepted_receipts").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ai" / "dropbox" / "research").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ai" / "dropbox" / "build").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ai" / "dropbox" / "state" / "runtime").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "paper_runtime" / "cycles").mkdir(parents=True, exist_ok=True)
    (repo_root / "data" / "db").mkdir(parents=True, exist_ok=True)
    return repo_root


def seed_receipts(repo_root: Path, lane_story_id: str = "LABEL-001") -> None:
    state_root = repo_root / ".ai" / "dropbox" / "state"
    write_json(state_root / "docs_truth_receipt.json", {"story_id": "LABEL-001"})
    write_json(state_root / "story_promotion_receipt.json", {"story_id": "LABEL-001"})
    write_json(state_root / "lane_health.json", {"activeStoryId": lane_story_id})


def packet_summaries(repo_root: Path, trigger_type: str) -> list[dict[str, object]]:
    summary_paths = sorted((repo_root / "data" / "reports" / "watcher" / trigger_type).glob("*/summary.json"))
    return [json.loads(path.read_text(encoding="utf-8")) for path in summary_paths]


def test_truth_drift_uses_prd_as_canonical_story(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    seed_receipts(repo_root, lane_story_id="EXEC-001")
    watcher = load_watch_module()

    result = watcher.main(["--repo", str(repo_root), "--once"])

    assert result == 0
    truth_drift_packets = packet_summaries(repo_root, "truth_drift")
    assert len(truth_drift_packets) == 1
    assert truth_drift_packets[0]["canonical_story_id"] == "LABEL-001"
    assert truth_drift_packets[0]["consistency_status"] == "truth_drift"
    assert packet_summaries(repo_root, "story_promotion_changed") == []
    assert packet_summaries(repo_root, "strategy_report_changed") == []
    assert packet_summaries(repo_root, "paper_cycle_closed") == []


def test_story_promotion_packet_emits_when_receipts_change(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    seed_receipts(repo_root)
    watcher = load_watch_module()

    result = watcher.main(["--repo", str(repo_root), "--once"])

    assert result == 0
    packets = packet_summaries(repo_root, "story_promotion_changed")
    assert len(packets) == 1
    assert packets[0]["recommended_route"] == "plan"
    assert packets[0]["sandbox_used"] is False


def test_strategy_report_packet_emits_when_report_changes(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    seed_receipts(repo_root)
    write_json(
        repo_root / ".ai" / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json",
        {"run_id": "run-001", "top_family": "trend_continuation_long_v1"},
    )
    watcher = load_watch_module()

    result = watcher.main(["--repo", str(repo_root), "--once"])

    assert result == 0
    packets = packet_summaries(repo_root, "strategy_report_changed")
    assert len(packets) == 1
    assert packets[0]["recommended_route"] == "task"
    assert packets[0]["canonical_story_id"] == "LABEL-001"


def test_lock_prevents_second_invocation(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    seed_receipts(repo_root)
    watcher = load_watch_module()
    script_path = REPO_ROOT / "scripts" / "agents" / "codex_watch_adapter.py"

    with watcher.process_lock(repo_root, mode="once"):
        metadata = watcher.read_lock_metadata(repo_root)
        assert metadata is not None
        assert metadata["mode"] == "once"
        completed = subprocess.run(
            [sys.executable, str(script_path), "--repo", str(repo_root), "--once"],
            text=True,
            capture_output=True,
            check=False,
        )

    assert completed.returncode == watcher.EXIT_LOCKED
    assert "watcher lock is already held" in completed.stderr


def test_paper_cycle_packets_emit_once(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    seed_receipts(repo_root)
    cycle_dir = repo_root / "data" / "paper_runtime" / "cycles" / "session-001"
    cycle_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        cycle_dir / "cycle_summary.json",
        {"session_key": "session-001", "filled": True, "session_status": "closed"},
    )
    (cycle_dir / "report.qmd").write_text("# Session 001\n", encoding="utf-8")
    watcher = load_watch_module()

    first = watcher.main(["--repo", str(repo_root), "--once"])
    second = watcher.main(["--repo", str(repo_root), "--once"])

    assert first == 0
    assert second == 0
    packets = packet_summaries(repo_root, "paper_cycle_closed")
    assert len(packets) == 1
    assert packets[0]["observed_inputs"][0].endswith("cycle_summary.json")


def test_ai_audit_classifies_delete_candidate_and_archives_ignored_outputs(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    seed_receipts(repo_root)
    (repo_root / ".ai" / "agents").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ai" / "agents" / "README.md").write_text("legacy\n", encoding="utf-8")
    (repo_root / ".ai" / "dropbox" / "build" / "ORCH-005__delivery.md").write_text(
        "done story residue\n",
        encoding="utf-8",
    )
    write_json(
        repo_root / ".ai" / "dropbox" / "state" / "accepted_receipts" / "ORCH-005__old.json",
        {"story_id": "ORCH-005", "accepted_at": "2026-04-16T00:00:00Z"},
    )
    write_json(
        repo_root / ".ai" / "dropbox" / "state" / "accepted_receipts" / "ORCH-005__new.json",
        {"story_id": "ORCH-005", "accepted_at": "2026-04-17T00:00:00Z"},
    )
    watcher = load_watch_module()

    result = watcher.main(["--repo", str(repo_root), "--once", "--audit-ai"])

    assert result == 0
    summary_path = next((repo_root / "data" / "reports" / "watcher" / "ai_hygiene").glob("*/summary.json"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    inventory = json.loads((summary_path.parent / "inventory.json").read_text(encoding="utf-8"))
    by_path = {entry["path"]: entry for entry in inventory}
    assert by_path[".ai/agents/README.md"]["classification"] == "delete_candidate"
    assert by_path[".ai/dropbox/build/ORCH-005__delivery.md"]["classification"] == "archive_ignored"
    assert by_path[".ai/dropbox/README.md"]["classification"] == "keep_policy"
    manifest_path = Path(summary["archive_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert ".ai/dropbox/build/ORCH-005__delivery.md" in manifest["copied_files"]


def test_sandbox_context_points_to_copied_db_paths(tmp_path: Path) -> None:
    repo_root = seed_repo(tmp_path)
    (repo_root / "src" / "d5_trading_engine").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "d5_trading_engine" / "__init__.py").write_text("", encoding="utf-8")
    (repo_root / "data" / "db" / "d5.db").write_text("truth\n", encoding="utf-8")
    (repo_root / "data" / "db" / "d5_analytics.duckdb").write_text("analytics\n", encoding="utf-8")
    (repo_root / "data" / "db" / "coinbase_raw.db").write_text("raw\n", encoding="utf-8")
    watcher = load_watch_module()

    sandbox_root: Path | None = None
    with watcher.sandbox_context(repo_root, "packet-001") as sandbox:
        sandbox_root = sandbox.root
        assert sandbox.repo_root == sandbox.root / "repo"
        assert Path(sandbox.env["REPO_ROOT"]) == sandbox.repo_root
        assert Path(sandbox.env["DATA_DIR"]) == sandbox.repo_root / "data"
        assert Path(sandbox.env["DB_PATH"]).read_text(encoding="utf-8") == "truth\n"
        assert Path(sandbox.env["DUCKDB_PATH"]).read_text(encoding="utf-8") == "analytics\n"
        assert Path(sandbox.env["COINBASE_RAW_DB_PATH"]).read_text(encoding="utf-8") == "raw\n"
        assert str(sandbox.repo_root / "src") in sandbox.env["PYTHONPATH"]

    assert sandbox_root is not None
    assert not sandbox_root.exists()
