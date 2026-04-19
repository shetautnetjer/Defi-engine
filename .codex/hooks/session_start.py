#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = REPO_ROOT / ".ai" / "dropbox" / "state"
LANE_STATE = REPO_ROOT / "training" / "automation" / "state" / "lane_sessions.json"
RESEARCH_PROFILES = REPO_ROOT / ".ai" / "profiles.toml"
RESEARCH_PROFILE_SCHEMA = REPO_ROOT / ".ai" / "schemas" / "profile.schema.json"
LOG_PATH = STATE_DIR / "codex_hook_session_start.jsonl"


def _read_hook_input() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return {}


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _selected_research_profile_name() -> str:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return "execution_cost_minimizer"
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, value = stripped.partition("=")
        if key == "TRADER_RESEARCH_PROFILE" and value:
            return value.strip().strip("\"'")
    return "execution_cost_minimizer"


def main() -> None:
    hook_input = _read_hook_input()
    trader_lane = {}
    if LANE_STATE.exists():
        try:
            lane_payload = json.loads(LANE_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            lane_payload = {}
        if isinstance(lane_payload, dict):
            trader_lane = lane_payload.get("trader", {})

    _append_jsonl(
        LOG_PATH,
        {
            "event": "SessionStart",
            "session_id": hook_input.get("session_id"),
            "cwd": hook_input.get("cwd"),
            "transcript_path": hook_input.get("transcript_path"),
            "trader_lane_session_id": trader_lane.get("session_id"),
        },
    )

    context = "\n".join(
        [
            "<trader_session_context>",
            "Read order:",
            "1. AGENTS.md",
            "2. training/AGENTS.md",
            "3. .ai/profiles.toml",
            "4. .ai/schemas/profile.schema.json",
            "5. training/trading_agent_harness.md",
            "6. training/program.md",
            "7. training/rubrics/training_regime_rubric.md",
            "8. docs/task/trading_qmd_report_contract.md",
            f"Lane registry: {LANE_STATE}",
            f"Research profile catalog: {RESEARCH_PROFILES}",
            f"Research profile schema: {RESEARCH_PROFILE_SCHEMA}",
            f"Selected research profile: {_selected_research_profile_name()}",
            "Named persistent lane: trader",
            "Fresh bounded lane: task",
            "</trader_session_context>",
        ]
    )

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": context,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - best effort hook
        print(f"[trader-hook] SessionStart error: {exc}", file=sys.stderr)
        sys.exit(0)
