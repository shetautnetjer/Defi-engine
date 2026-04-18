#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from codex_watch_adapter import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main(["--once", "--audit-ai", *sys.argv[1:]]))
