#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LOG_PATH = REPO_ROOT / ".ai" / "dropbox" / "state" / "codex_post_tool_use.jsonl"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        payload = {}

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - best effort hook
        print(f"[trader-hook] PostToolUse error: {exc}", file=sys.stderr)
        sys.exit(0)
