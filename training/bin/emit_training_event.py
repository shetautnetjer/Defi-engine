#!/usr/bin/env python3
"""Append one bounded training event into the automation queue."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys
import uuid

import orjson


def _load_payload(path: Path | None) -> dict:
    if path is None:
        return {}
    try:
        payload = orjson.loads(path.read_bytes())
    except FileNotFoundError as exc:
        raise SystemExit(f"payload file not found: {path}") from exc
    except orjson.JSONDecodeError as exc:
        raise SystemExit(f"payload file is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("payload file must decode to a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--payload-path", type=Path, default=None)
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("training/automation/state/events.jsonl"),
    )
    parser.add_argument("--owner-kind", default="training")
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()

    payload = _load_payload(args.payload_path)
    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": args.event_type,
        "owner_kind": args.owner_kind,
        "run_id": args.run_id or payload.get("run_id", ""),
        "occurred_at_utc": datetime.now(UTC).isoformat(),
        "payload": payload,
    }

    args.queue.parent.mkdir(parents=True, exist_ok=True)
    with args.queue.open("ab") as handle:
        handle.write(orjson.dumps(event))
        handle.write(b"\n")

    sys.stdout.write(orjson.dumps(event, option=orjson.OPT_INDENT_2).decode())
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
