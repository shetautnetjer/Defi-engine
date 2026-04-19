from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "training" / "bin" / "resolve_training_context.py"
RENDER_PROMPT = REPO_ROOT / "training" / "automation" / "bin" / "render_prompt.py"
DISPATCH = REPO_ROOT / "training" / "automation" / "bin" / "codex_dispatch.sh"
WATCHER = REPO_ROOT / "training" / "automation" / "bin" / "codex_event_watcher.py"
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
        repo_root / ".ai" / "policies" / "profile_router_policy.v1.json",
        json.dumps({"policy_id": "profile_router_policy_v1"}),
    )
    _write(
        repo_root / ".ai" / "schemas" / "meta_governor_scorecard.schema.json",
        json.dumps({"title": "scorecard"}),
    )
    _write(
        repo_root / ".ai" / "schemas" / "profile_governor_decision.schema.json",
        json.dumps({"title": "decision"}),
    )
    _write(repo_root / ".codex" / "config.toml", "model = \"gpt-5.4\"\n")
    _write(repo_root / ".codex" / "hooks.json", "{\"hooks\": {}}\n")
    _write(repo_root / "training" / "automation" / "state" / ".gitkeep", "")
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
    assert payload["doc_paths"]["research_profiles"] == ".ai/profiles.toml"
    assert payload["doc_paths"]["research_profile_schema"] == ".ai/schemas/profile.schema.json"
    assert payload["doc_paths"]["governor_policy"] == ".ai/policies/profile_router_policy.v1.json"
    assert payload["active_profile_revision_id"] == "paper_profile_revision_fixture"
    assert payload["selected_research_profile_name"] == "execution_cost_minimizer"
    assert "execution / intraday" in payload["selected_research_profile_summary"]
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
    assert "Selected research profile:" in rendered
    assert "execution_cost_minimizer" in rendered
    assert "execution / intraday" in rendered
    assert "profile_router_policy.v1.json" in rendered


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
    assert "- lane_name: trader" in receipt
    assert "- dispatch_mode: persistent" in receipt
    assert "- codex_profile: trader" in receipt


def test_rules_example_declares_trader_and_task_lanes() -> None:
    payload = json.loads(RULES.read_text(encoding="utf-8"))

    defaults = payload["defaults"]
    assert defaults["lane_name"] == "task"
    assert defaults["dispatch_mode"] == "fresh"
    assert defaults["codex_profile"] == "task"

    paper = payload["event_types"]["paper_session_closed"]
    assert paper["lane_name"] == "trader"
    assert paper["dispatch_mode"] == "persistent"
    assert paper["codex_profile"] == "trader"

    feature = payload["event_types"]["feature_run_completed"]
    assert feature["lane_name"] == "task"
    assert feature["dispatch_mode"] == "fresh"
    assert feature["codex_profile"] == "task"


def test_codex_dispatch_initializes_persistent_trader_lane_and_records_session(tmp_path: Path) -> None:
    event_path = _make_training_fixture(tmp_path)
    receipts_dir = tmp_path / "receipts"
    args_log = tmp_path / "codex_args.log"
    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGS_LOG\"\n"
        "if [[ \"$1\" == \"--help\" ]]; then\n"
        "  echo 'usage: codex exec review';\n"
        "  exit 0\n"
        "fi\n"
        "last_message=''\n"
        "for ((i=1; i<=$#; i++)); do\n"
        "  if [[ \"${!i}\" == \"--output-last-message\" ]]; then\n"
        "    j=$((i+1))\n"
        "    last_message=\"${!j}\"\n"
        "  fi\n"
        "done\n"
        "printf 'last message\\n' > \"$last_message\"\n"
        "echo '{\"session_id\":\"sess-trader-1\",\"thread_id\":\"thread-trader-1\",\"event\":\"session.created\"}'\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = os.environ.copy()
    env["CODEX_BIN"] = str(fake_codex)
    env["CODEX_ARGS_LOG"] = str(args_log)
    subprocess.run(
        [
            "bash",
            str(DISPATCH),
            "--event-file",
            str(event_path),
            "--rules",
            str(RULES),
            "--receipts-dir",
            str(receipts_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    lane_sessions = json.loads(
        (tmp_path / "training" / "automation" / "state" / "lane_sessions.json").read_text(encoding="utf-8")
    )
    trader = lane_sessions["trader"]
    assert trader["mode"] == "persistent"
    assert trader["profile"] == "trader"
    assert trader["session_id"] == "sess-trader-1"
    assert trader["thread_id"] == "thread-trader-1"
    assert trader["last_event_id"] == "evt-paper-1"

    args_used = args_log.read_text(encoding="utf-8")
    assert "exec" in args_used
    assert "resume" not in args_used
    assert "trader" in args_used

    receipt = (receipts_dir / "paper_evt-paper-1.md").read_text(encoding="utf-8")
    assert "- session_action: initialized" in receipt
    assert "- session_id: sess-trader-1" in receipt
    assert "- thread_id: thread-trader-1" in receipt


def test_codex_dispatch_resumes_existing_trader_lane(tmp_path: Path) -> None:
    event_path = _make_training_fixture(tmp_path)
    receipts_dir = tmp_path / "receipts"
    args_log = tmp_path / "codex_args.log"
    lane_state_path = tmp_path / "training" / "automation" / "state" / "lane_sessions.json"
    lane_state_path.write_text(
        json.dumps(
            {
                "trader": {
                    "lane_name": "trader",
                    "mode": "persistent",
                    "profile": "trader",
                    "session_id": "sess-existing",
                    "thread_id": "thread-existing",
                    "last_event_id": "evt-old",
                    "last_receipt_path": "receipts/old.md",
                    "updated_at_utc": "2026-04-19T00:00:00Z",
                    "stale_after_hours": 24,
                }
            }
        ),
        encoding="utf-8",
    )
    fake_codex = tmp_path / "fake_codex.sh"
    fake_codex.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%s\\n' \"$@\" > \"$CODEX_ARGS_LOG\"\n"
        "if [[ \"$1\" == \"--help\" ]]; then\n"
        "  echo 'usage: codex exec review';\n"
        "  exit 0\n"
        "fi\n"
        "last_message=''\n"
        "for ((i=1; i<=$#; i++)); do\n"
        "  if [[ \"${!i}\" == \"--output-last-message\" ]]; then\n"
        "    j=$((i+1))\n"
        "    last_message=\"${!j}\"\n"
        "  fi\n"
        "done\n"
        "printf 'last message\\n' > \"$last_message\"\n"
        "echo '{\"session_id\":\"sess-existing\",\"thread_id\":\"thread-existing\",\"event\":\"turn.completed\"}'\n",
        encoding="utf-8",
    )
    fake_codex.chmod(0o755)

    env = os.environ.copy()
    env["CODEX_BIN"] = str(fake_codex)
    env["CODEX_ARGS_LOG"] = str(args_log)
    subprocess.run(
        [
            "bash",
            str(DISPATCH),
            "--event-file",
            str(event_path),
            "--rules",
            str(RULES),
            "--receipts-dir",
            str(receipts_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    args_used = args_log.read_text(encoding="utf-8")
    assert "resume" in args_used
    assert "sess-existing" in args_used

    lane_sessions = json.loads(lane_state_path.read_text(encoding="utf-8"))
    trader = lane_sessions["trader"]
    assert trader["session_id"] == "sess-existing"
    assert trader["last_event_id"] == "evt-paper-1"

    receipt = (receipts_dir / "paper_evt-paper-1.md").read_text(encoding="utf-8")
    assert "- session_action: resumed" in receipt
    assert "- session_id: sess-existing" in receipt


def test_event_watcher_writes_trader_lane_status(tmp_path: Path) -> None:
    event_path = _make_training_fixture(tmp_path)
    queue_path = tmp_path / "training" / "automation" / "state" / "events.jsonl"
    queue_payload = json.loads(event_path.read_text(encoding="utf-8"))
    queue_path.write_text(json.dumps(queue_payload) + "\n", encoding="utf-8")
    state_path = tmp_path / "training" / "automation" / "state" / "watcher_state.json"
    status_path = tmp_path / "training" / "automation" / "state" / "watcher_status.json"
    receipts_dir = tmp_path / "receipts"
    dispatch_script = tmp_path / "fake_dispatch.sh"
    dispatch_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "event_file=''\n"
        "receipts_dir=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    --event-file) event_file=\"$2\"; shift 2 ;;\n"
        "    --receipts-dir) receipts_dir=\"$2\"; shift 2 ;;\n"
        "    --rules) shift 2 ;;\n"
        "    --dry-run) shift ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "repo_root=$(python3 - <<'PY' \"$event_file\"\n"
        "import json, pathlib, sys\n"
        "print(json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['repo_root'])\n"
        "PY\n"
        ")\n"
        "mkdir -p \"$receipts_dir\" \"$repo_root/training/automation/state\"\n"
        "cat > \"$repo_root/training/automation/state/lane_sessions.json\" <<'JSON'\n"
        "{\n"
        "  \"trader\": {\n"
        "    \"lane_name\": \"trader\",\n"
        "    \"mode\": \"persistent\",\n"
        "    \"profile\": \"trader\",\n"
        "    \"session_id\": \"sess-watcher\",\n"
        "    \"thread_id\": \"thread-watcher\",\n"
        "    \"last_event_id\": \"evt-paper-1\",\n"
        "    \"last_receipt_path\": \"receipts/paper_evt-paper-1.md\",\n"
        "    \"updated_at_utc\": \"2026-04-19T13:00:00Z\",\n"
        "    \"stale_after_hours\": 24\n"
        "  }\n"
        "}\n"
        "JSON\n"
        "echo 'ok' > \"$receipts_dir/paper_evt-paper-1.md\"\n",
        encoding="utf-8",
    )
    dispatch_script.chmod(0o755)

    subprocess.run(
        [
            "python3",
            str(WATCHER),
            "--queue",
            str(queue_path),
            "--rules",
            str(RULES),
            "--state-file",
            str(state_path),
            "--status-file",
            str(status_path),
            "--receipts-dir",
            str(receipts_dir),
            "--dispatch-script",
            str(dispatch_script),
            "--once",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    watcher_status = json.loads(status_path.read_text(encoding="utf-8"))
    assert watcher_status["status"] == "once_complete"
    assert watcher_status["processed_count"] == 1
    assert watcher_status["last_event_id"] == "evt-paper-1"
    assert watcher_status["last_event_type"] == "paper_session_closed"
    assert watcher_status["last_dispatch_ok"] is True
    assert watcher_status["trader_lane"]["session_id"] == "sess-watcher"
    assert watcher_status["trader_lane"]["profile"] == "trader"
