#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import fcntl
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FINDER_STATE_DEFAULTS: dict[str, Any] = {
    "pendingTrigger": None,
    "queuedReceiptFollowons": [],
    "lastProcessedReceiptId": "",
    "lastProcessedFailureSignature": "",
    "lastProcessedCompletionScope": "",
    "lastProcessedPerformanceReceiptId": "",
    "lastTerminalAuditAt": "",
    "lastFinderAuditId": "",
    "lastWriterDecisionId": "",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def deep_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def state_dir(repo_root: Path) -> Path:
    return repo_root / ".ai" / "dropbox" / "state"


def finder_state_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "finder_state.json"


def finder_decision_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "finder_decision.json"


def completion_writer_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "completion_audit_writer.json"


def mailbox_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "mailbox.jsonl"


def performance_receipts_dir(repo_root: Path) -> Path:
    return state_dir(repo_root) / "performance_receipts"


def accepted_receipts_dir(repo_root: Path) -> Path:
    return state_dir(repo_root) / "accepted_receipts"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deep_copy(default)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deep_copy(default)
    if isinstance(default, dict) and not isinstance(loaded, dict):
        return deep_copy(default)
    if isinstance(default, list) and not isinstance(loaded, list):
        return deep_copy(default)
    return loaded


def normalize_finder_state(doc: dict[str, Any]) -> dict[str, Any]:
    state = deep_copy(FINDER_STATE_DEFAULTS)
    if isinstance(doc, dict):
        state.update(doc)
    if state.get("pendingTrigger") is not None and not isinstance(
        state["pendingTrigger"], dict
    ):
        state["pendingTrigger"] = None
    for key in ("queuedReceiptFollowons",):
        if not isinstance(state.get(key), list):
            state[key] = []
    for key in (
        "lastProcessedReceiptId",
        "lastProcessedFailureSignature",
        "lastProcessedCompletionScope",
        "lastProcessedPerformanceReceiptId",
        "lastTerminalAuditAt",
        "lastFinderAuditId",
        "lastWriterDecisionId",
    ):
        state[key] = str(state.get(key) or "")
    return state


def atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


@contextmanager
def locked_state(repo_root: Path):
    state_root = state_dir(repo_root)
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = state_root / "swarm_state.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_finder_state(repo_root: Path) -> dict[str, Any]:
    return normalize_finder_state(read_json(finder_state_path(repo_root), {}))


def write_finder_state(repo_root: Path, state: dict[str, Any]) -> None:
    atomic_write_json(finder_state_path(repo_root), normalize_finder_state(state))


def queue_receipt_followons(repo_root: Path) -> None:
    with locked_state(repo_root):
        state = load_finder_state(repo_root)
        matches = sorted(accepted_receipts_dir(repo_root).glob("*.json"))
        if not matches:
            return

        latest = read_json(matches[-1], {})
        receipt_id = str(latest.get("receipt_id") or "")
        if not receipt_id or state.get("lastProcessedReceiptId") == receipt_id:
            return

        queued = list(state.get("queuedReceiptFollowons") or [])
        needs_followon = any(
            latest.get(key)
            for key in ("contradictions_found", "unresolved_risks", "promotion_targets")
        )
        if needs_followon and all(
            item.get("receiptId") != receipt_id for item in queued if isinstance(item, dict)
        ):
            queued.append(
                {
                    "receiptId": receipt_id,
                    "storyId": str(latest.get("story_id") or ""),
                    "queuedAt": str(latest.get("timestamp") or ""),
                }
            )
        state["queuedReceiptFollowons"] = queued
        state["lastProcessedReceiptId"] = receipt_id
        write_finder_state(repo_root, state)


def queue_performance_trigger(repo_root: Path) -> None:
    with locked_state(repo_root):
        state = load_finder_state(repo_root)
        if state.get("pendingTrigger"):
            return

        matches = sorted(performance_receipts_dir(repo_root).glob("*.json"))
        if not matches:
            return

        latest = read_json(matches[-1], {})
        receipt_id = str(latest.get("receipt_id") or "")
        recommendation = str(latest.get("recommendation") or "")
        if (
            not receipt_id
            or receipt_id == state.get("lastProcessedPerformanceReceiptId")
        ):
            return

        state["lastProcessedPerformanceReceiptId"] = receipt_id
        if recommendation == "no_action":
            write_finder_state(repo_root, state)
            return

        scope = f"performance_{str(latest.get('experiment_run_id') or 'audit')}"
        scope = scope.replace("/", "_").replace(":", "_")
        state["pendingTrigger"] = {
            "triggerId": f"performance::{receipt_id}",
            "triggerType": "performance_receipt",
            "scope": scope,
            "storyId": "",
            "performanceReceiptId": receipt_id,
            "createdAt": str(latest.get("timestamp") or ""),
        }
        write_finder_state(repo_root, state)


def queue_repeated_failure_trigger(repo_root: Path) -> None:
    with locked_state(repo_root):
        state = load_finder_state(repo_root)
        if state.get("pendingTrigger"):
            return

        events: list[dict[str, Any]] = []
        for raw in mailbox_path(repo_root).read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if doc.get("type") != "lane_status":
                continue
            if doc.get("status") not in {"failed", "stale", "blocked"}:
                continue
            events.append(doc)

        if len(events) < 2:
            return

        last = events[-1]
        prev = events[-2]
        signature = "|".join(
            [
                str(last.get("storyId") or ""),
                str(last.get("lane") or ""),
                str(last.get("status") or ""),
                str(last.get("reason") or ""),
            ]
        )
        prev_signature = "|".join(
            [
                str(prev.get("storyId") or ""),
                str(prev.get("lane") or ""),
                str(prev.get("status") or ""),
                str(prev.get("reason") or ""),
            ]
        )
        if not signature or signature != prev_signature:
            return
        if state.get("lastProcessedFailureSignature") == signature:
            return

        state["pendingTrigger"] = {
            "triggerId": f"finder::{last.get('ts', '')}::{last.get('storyId', '')}",
            "triggerType": "repeated_failure",
            "scope": str(last.get("storyId") or ""),
            "storyId": str(last.get("storyId") or ""),
            "failureSignature": signature,
            "createdAt": str(last.get("ts") or ""),
        }
        state["lastProcessedFailureSignature"] = signature
        write_finder_state(repo_root, state)


def queue_completion_trigger(repo_root: Path) -> None:
    with locked_state(repo_root):
        prd = read_json(repo_root / "prd.json", {})
        eligible_states = {"ready", "active", "recovery"}
        if any(
            story.get("state") in eligible_states
            for story in prd.get("userStories", [])
            if isinstance(story, dict)
        ):
            return

        state = load_finder_state(repo_root)
        if state.get("pendingTrigger"):
            return

        latest_receipt = ""
        matches = sorted(accepted_receipts_dir(repo_root).glob("*.json"))
        if matches:
            latest = read_json(matches[-1], {})
            latest_receipt = str(latest.get("receipt_id") or "")

        scope_signature = f"completion_audit::{latest_receipt}"
        if state.get("lastProcessedCompletionScope") == scope_signature:
            return

        state["pendingTrigger"] = {
            "triggerId": scope_signature,
            "triggerType": "completion_audit",
            "scope": "completion_audit",
            "storyId": str(prd.get("activeStoryId") or ""),
            "sourceReceiptId": latest_receipt,
            "createdAt": utc_now(),
        }
        write_finder_state(repo_root, state)


def queue_periodic_terminal_audit(repo_root: Path) -> None:
    with locked_state(repo_root):
        prd = read_json(repo_root / "prd.json", {})
        if str(prd.get("swarmState") or "") != "terminal_complete":
            return

        state = load_finder_state(repo_root)
        if state.get("pendingTrigger"):
            return

        last_audit_at = str(state.get("lastTerminalAuditAt") or "")
        if last_audit_at:
            try:
                last_epoch = datetime.fromisoformat(
                    last_audit_at.replace("Z", "+00:00")
                ).timestamp()
                now_epoch = datetime.now(timezone.utc).timestamp()
                if (now_epoch - last_epoch) < 3600:
                    return
            except ValueError:
                pass

        timestamp = utc_now()
        state["pendingTrigger"] = {
            "triggerId": f"periodic_completion_audit::{timestamp}",
            "triggerType": "periodic_completion_audit",
            "scope": "completion_audit",
            "storyId": "",
            "sourceReceiptId": str(prd.get("lastCompletionAuditReceiptId") or ""),
            "createdAt": timestamp,
        }
        write_finder_state(repo_root, state)


def clear_stale_completion_trigger(repo_root: Path) -> None:
    with locked_state(repo_root):
        prd = read_json(repo_root / "prd.json", {})
        state = load_finder_state(repo_root)
        pending = state.get("pendingTrigger") or {}
        trigger_type = str(pending.get("triggerType") or "")
        if trigger_type not in {"completion_audit", "periodic_completion_audit"}:
            return

        eligible_states = {"ready", "active", "recovery"}
        has_eligible = any(
            story.get("state") in eligible_states
            for story in prd.get("userStories", [])
            if isinstance(story, dict)
        )
        if not has_eligible:
            return

        state["pendingTrigger"] = None
        write_finder_state(repo_root, state)


def clear_processed_finder(repo_root: Path) -> None:
    with locked_state(repo_root):
        state = load_finder_state(repo_root)
        pending = state.get("pendingTrigger") or {}
        scope = str(pending.get("scope") or "")
        trigger_type = str(pending.get("triggerType") or "")

        decision_id = ""
        if scope == "completion_audit" and completion_writer_path(repo_root).exists():
            doc = read_json(completion_writer_path(repo_root), {})
            decision_id = str(doc.get("audit_id") or "")
        elif finder_decision_path(repo_root).exists():
            doc = read_json(finder_decision_path(repo_root), {})
            decision_id = str(doc.get("decision_id") or "")

        state["pendingTrigger"] = None
        if trigger_type in {"completion_audit", "periodic_completion_audit"}:
            state["lastProcessedCompletionScope"] = (
                f"completion_audit::{pending.get('sourceReceiptId') or ''}"
            )
            state["queuedReceiptFollowons"] = []
            state["lastTerminalAuditAt"] = utc_now()
        if decision_id:
            state["lastFinderAuditId"] = decision_id
            state["lastWriterDecisionId"] = decision_id
        write_finder_state(repo_root, state)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mutate Defi-engine finder and completion-audit state under a lock."
    )
    parser.add_argument("--repo", required=True, help="Repo root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in (
        "queue-receipt-followons",
        "queue-performance-trigger",
        "queue-repeated-failure-trigger",
        "queue-completion-trigger",
        "queue-periodic-terminal-audit",
        "clear-stale-completion-trigger",
        "clear-processed-finder",
    ):
        subparsers.add_parser(name)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo).resolve()
    commands = {
        "queue-receipt-followons": queue_receipt_followons,
        "queue-performance-trigger": queue_performance_trigger,
        "queue-repeated-failure-trigger": queue_repeated_failure_trigger,
        "queue-completion-trigger": queue_completion_trigger,
        "queue-periodic-terminal-audit": queue_periodic_terminal_audit,
        "clear-stale-completion-trigger": clear_stale_completion_trigger,
        "clear-processed-finder": clear_processed_finder,
    }
    commands[args.command](repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
