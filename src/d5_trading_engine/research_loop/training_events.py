"""Thin training-automation event helpers for watcher-driven Codex review."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable
import uuid

import orjson

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.config.settings import Settings

log = get_logger(__name__, component="training_events")


def _normalize_relpaths(
    repo_root: Path,
    values: Iterable[str | Path] | None,
) -> list[str]:
    normalized: list[str] = []
    if not values:
        return normalized
    for value in values:
        path = Path(value)
        if not path.is_absolute():
            path = repo_root / path
        try:
            normalized.append(path.resolve().relative_to(repo_root.resolve()).as_posix())
        except ValueError:
            normalized.append(str(path.resolve()))
    return normalized


def build_training_event(
    settings: Settings,
    *,
    event_type: str,
    summary: str,
    owner_kind: str = "training",
    run_id: str = "",
    qmd_reports: Iterable[str | Path] | None = None,
    sql_refs: Iterable[str] | None = None,
    context_files: Iterable[str | Path] | None = None,
    log_files: Iterable[str | Path] | None = None,
    notes: str = "",
    session_id: str = "",
    thread_id: str = "",
    turn_id: str = "",
    hook_name: str = "",
) -> dict[str, object]:
    repo_root = settings.repo_root.resolve()
    event: dict[str, object] = {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "owner_kind": owner_kind,
        "run_id": run_id,
        "occurred_at_utc": datetime.now(UTC).isoformat(),
        "repo_root": str(repo_root),
        "summary": summary,
    }
    if qmd_reports:
        event["qmd_reports"] = _normalize_relpaths(repo_root, qmd_reports)
    if sql_refs:
        event["sql_refs"] = [str(item) for item in sql_refs]
    if context_files:
        event["context_files"] = _normalize_relpaths(repo_root, context_files)
    if log_files:
        event["log_files"] = _normalize_relpaths(repo_root, log_files)
    if notes:
        event["notes"] = notes
    if session_id:
        event["session_id"] = session_id
    if thread_id:
        event["thread_id"] = thread_id
    if turn_id:
        event["turn_id"] = turn_id
    if hook_name:
        event["hook_name"] = hook_name
    return event


def append_training_event(
    settings: Settings,
    *,
    event_type: str,
    summary: str,
    owner_kind: str = "training",
    run_id: str = "",
    qmd_reports: Iterable[str | Path] | None = None,
    sql_refs: Iterable[str] | None = None,
    context_files: Iterable[str | Path] | None = None,
    log_files: Iterable[str | Path] | None = None,
    notes: str = "",
    queue_path: Path | None = None,
    session_id: str = "",
    thread_id: str = "",
    turn_id: str = "",
    hook_name: str = "",
) -> dict[str, object]:
    event = build_training_event(
        settings,
        event_type=event_type,
        summary=summary,
        owner_kind=owner_kind,
        run_id=run_id,
        qmd_reports=qmd_reports,
        sql_refs=sql_refs,
        context_files=context_files,
        log_files=log_files,
        notes=notes,
        session_id=session_id,
        thread_id=thread_id,
        turn_id=turn_id,
        hook_name=hook_name,
    )
    queue = queue_path or (
        settings.repo_root / "training" / "automation" / "state" / "events.jsonl"
    )
    queue.parent.mkdir(parents=True, exist_ok=True)
    with queue.open("ab") as handle:
        handle.write(orjson.dumps(event))
        handle.write(b"\n")
    return event


def append_training_event_safe(
    settings: Settings,
    *,
    event_type: str,
    summary: str,
    owner_kind: str = "training",
    run_id: str = "",
    qmd_reports: Iterable[str | Path] | None = None,
    sql_refs: Iterable[str] | None = None,
    context_files: Iterable[str | Path] | None = None,
    log_files: Iterable[str | Path] | None = None,
    notes: str = "",
    queue_path: Path | None = None,
    session_id: str = "",
    thread_id: str = "",
    turn_id: str = "",
    hook_name: str = "",
) -> dict[str, object] | None:
    try:
        return append_training_event(
            settings,
            event_type=event_type,
            summary=summary,
            owner_kind=owner_kind,
            run_id=run_id,
            qmd_reports=qmd_reports,
            sql_refs=sql_refs,
            context_files=context_files,
            log_files=log_files,
            notes=notes,
            queue_path=queue_path,
            session_id=session_id,
            thread_id=thread_id,
            turn_id=turn_id,
            hook_name=hook_name,
        )
    except Exception as exc:  # pragma: no cover - fail-open by design
        log.warning(
            "training_event_emit_failed",
            event_type=event_type,
            run_id=run_id,
            error=str(exc),
        )
        return None
