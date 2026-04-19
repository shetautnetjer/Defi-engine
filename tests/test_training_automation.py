from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "training" / "bin" / "resolve_training_context.py"
RENDER_PROMPT = REPO_ROOT / "training" / "automation" / "bin" / "render_prompt.py"
DISPATCH = REPO_ROOT / "training" / "automation" / "bin" / "codex_dispatch.sh"
RULES = REPO_ROOT / "training" / "automation" / "config" / "automation_rules.example.json"
PAPER_TEMPLATE = REPO_ROOT / "training" / "automation" / "prompts" / "paper_session_review.md.tmpl"


def _write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def _make_training_fixture(repo_root: Path) -> Path:
    _write(repo_root / "AGENTS.md", "# Root agents\n")
    _write(repo_root / "training" / "AGENTS.md", "# Training agents\n")
    _write(repo_root / "training" / "README.md", "# Training readme\n")
    _write(repo_root / "training" / "trading_agent_harness.md", "# Harness\n")
    _write(repo_root / "training" / "program.md", "# Program\n")
    _write(repo_root / "training" / "rubrics" / "training_regime_rubric.md", "# Rubric\n")
    _write(repo_root / "docs" / "task" / "trading_qmd_report_contract.md", "# QMD contract\n")
    _write(
        repo_root / ".ai" / "dropbox" / "state" / "paper_practice_status.json",
        json.dumps(
            {
                "active_revision_id": "paper_profile_revision_live",
                "latest_loop_run_id": "loop_run_live",
                "open_session_key": "",
                "historical_cache_status": {
                    "complete": False,
                    "completed_day_count": 12,
                    "missing_day_count": 718,
                    "next_missing_date": "2024-04-01",
                },
            }
        ),
    )
    _write(
        repo_root / ".ai" / "dropbox" / "state" / "paper_practice_latest_profile_revision.json",
        json.dumps({"revision_id": "paper_profile_revision_fixture"}),
    )
    _write(
        repo_root / ".ai" / "dropbox" / "state" / "paper_practice_latest_trade_receipt.json",
        json.dumps({"session_key": "paper_session_fixture", "close_reason": "time_stop"}),
    )
    _write(
        repo_root / ".ai" / "dropbox" / "state" / "source_collection_status.json",
        json.dumps(
            {
                "historical_cache_after": {
                    "complete": False,
                    "completed_day_count": 14,
                    "missing_day_count": 716,
                    "next_missing_date": "2024-04-03",
                }
            }
        ),
    )
    _write(
        repo_root / "data" / "research" / "training" / "reviews" / "training_review_fixture" / "summary.json",
        json.dumps({"latest_backtest_run_id": "backtest_run_fixture"}),
    )
    _write(
        repo_root / "data" / "research" / "training" / "reviews" / "training_review_fixture" / "report.qmd",
        "# review\n",
    )
    _write(
        repo_root / "data" / "research" / "paper_practice" / "backtests" / "backtest_fixture" / "summary.json",
        json.dumps({"run_id": "backtest_run_fixture"}),
    )
    _write(
        repo_root / "data" / "research" / "paper_practice" / "backtests" / "backtest_fixture" / "report.qmd",
        "# backtest\n",
    )
    _write(
        repo_root / "data" / "research" / "paper_practice" / "bootstrap" / "bootstrap_fixture" / "bootstrap_summary.json",
        json.dumps({"bootstrap_id": "bootstrap_fixture"}),
    )
    _write(
        repo_root / "data" / "research" / "paper_practice" / "bootstrap" / "bootstrap_fixture" / "report.qmd",
        "# bootstrap\n",
    )
    _write(repo_root / "docs" / "reports" / "paper_session_fixture.qmd", "# paper session report\n")

    event_path = repo_root / "event.json"
    event_path.write_text(
        json.dumps(
            {
                "event_id": "evt-paper-1",
                "event_type": "paper_session_closed",
                "repo_root": str(repo_root),
                "summary": "Closed a paper session after a time stop.",
                "qmd_reports": ["docs/reports/paper_session_fixture.qmd"],
                "sql_refs": ["sqlite:///data/truth/d5.sqlite#paper_session=88"],
                "context_files": ["src/d5_trading_engine/paper_runtime/practice.py"],
                "notes": "Review the close and propose one bounded next change.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return event_path


def test_resolve_training_context_uses_repo_doctrine_and_recent_artifacts(tmp_path: Path) -> None:
    event_path = _make_training_fixture(tmp_path)
    result = subprocess.run(
        ["python3", str(HELPER), "--event-file", str(event_path), "--repo-root", str(tmp_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)

    assert payload["doc_paths"]["root_agents"] == "AGENTS.md"
    assert payload["doc_paths"]["trading_harness"] == "training/trading_agent_harness.md"
    assert payload["doc_paths"]["qmd_contract"] == "docs/task/trading_qmd_report_contract.md"
    assert payload["active_profile_revision_id"] == "paper_profile_revision_fixture"
    assert "closed-session evidence" in payload["keep_revert_shadow_rule"]
    assert "paper-profile" in payload["target_surface"]
    assert payload["primary_qmd_path"] == "docs/reports/paper_session_fixture.qmd"
    assert "backtest_summary_run_id=backtest_run_fixture" in payload["baseline_refs"]
    assert payload["resolved_sql_refs"] == ["sqlite:///data/truth/d5.sqlite#paper_session=88"]


def test_render_prompt_includes_harness_context_and_baseline(tmp_path: Path) -> None:
    event_path = _make_training_fixture(tmp_path)
    output_path = tmp_path / "rendered_prompt.md"
    subprocess.run(
        [
            "python3",
            str(RENDER_PROMPT),
            "--event-file",
            str(event_path),
            "--template",
            str(PAPER_TEMPLATE),
            "--receipt-path",
            str(tmp_path / "receipt.md"),
            "--output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=True,
    )

    rendered = output_path.read_text(encoding="utf-8")
    assert "training/trading_agent_harness.md" in rendered
    assert "Keep / revert / shadow rule:" in rendered
    assert "paper_profile_revision_fixture" in rendered
    assert "backtest_summary_run_id=backtest_run_fixture" in rendered
    assert "closed-session evidence" in rendered


def test_codex_dispatch_dry_run_uses_exec_json_and_repo_cd(tmp_path: Path) -> None:
    event_path = _make_training_fixture(tmp_path)
    receipts_dir = tmp_path / "receipts"
    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"$1\" == \"--help\" ]]; then\n"
        "  echo 'usage: codex exec review';\n"
        "  exit 0;\n"
        "fi\n"
        "echo 'unexpected invocation' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = os.environ.copy()
    env["CODEX_BIN"] = str(fake_codex)
    result = subprocess.run(
        [
            "bash",
            str(DISPATCH),
            "--event-file",
            str(event_path),
            "--rules",
            str(RULES),
            "--receipts-dir",
            str(receipts_dir),
            "--dry-run",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    assert "[dry-run] would run:" in result.stdout
    receipt_path = receipts_dir / "paper_evt-paper-1.md"
    receipt = receipt_path.read_text(encoding="utf-8")
    assert "codex_evt-paper-1.last_message.md" in receipt
    assert "--json" in receipt
    assert " -C " in result.stdout or " -C\\ " in result.stdout
    assert f"- repo_root: {tmp_path}" in receipt
