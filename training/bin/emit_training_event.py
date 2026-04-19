#!/usr/bin/env python3
"""Append one bounded training event into the automation queue."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

import orjson

from d5_trading_engine.config.settings import get_settings
from d5_trading_engine.research_loop.training_events import append_training_event


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


def _list_value(primary: list[str] | None, payload: dict, key: str) -> list[str]:
    if primary:
        return primary
    raw = payload.get(key)
    if isinstance(raw, list):
        return [str(item) for item in raw]
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-type", required=True)
    parser.add_argument("--payload-path", type=Path, default=None)
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument(
        "--queue",
        type=Path,
        default=Path("training/automation/state/events.jsonl"),
    )
    parser.add_argument("--owner-kind", default="training")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--qmd-report", action="append", default=None)
    parser.add_argument("--sql-ref", action="append", default=None)
    parser.add_argument("--context-file", action="append", default=None)
    parser.add_argument("--log-file", action="append", default=None)
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    payload = _load_payload(args.payload_path)
    settings = get_settings()
    if args.repo_root is not None:
        settings.repo_root = args.repo_root.resolve()
    qmd_reports = _list_value(args.qmd_report, payload, "qmd_reports")
    sql_refs = _list_value(args.sql_ref, payload, "sql_refs")
    context_files = _list_value(args.context_file, payload, "context_files")
    log_files = _list_value(args.log_file, payload, "log_files")

    event = append_training_event(
        settings,
        event_type=args.event_type,
        summary=args.summary or str(payload.get("summary", "")),
        owner_kind=args.owner_kind or str(payload.get("owner_kind", "training")),
        run_id=args.run_id or str(payload.get("run_id", "")),
        qmd_reports=qmd_reports,
        sql_refs=sql_refs,
        context_files=context_files,
        log_files=log_files,
        notes=args.note or str(payload.get("notes", "")),
        queue_path=args.queue,
        session_id=str(payload.get("session_id", "")),
        thread_id=str(payload.get("thread_id", "")),
        turn_id=str(payload.get("turn_id", "")),
        hook_name=str(payload.get("hook_name", "")),
    )

    sys.stdout.write(orjson.dumps(event, option=orjson.OPT_INDENT_2).decode())
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
