#!/usr/bin/env python3

from __future__ import annotations

import argparse
import contextlib
import copy
import fcntl
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml


EXIT_LOCKED = 75
LOCK_FILENAME = "watcher.lock"
DEFAULT_INTERVAL_SECONDS = 60


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def deep_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def atomic_write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp_path.write_text(contents, encoding="utf-8")
    os.replace(tmp_path, path)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return deep_copy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deep_copy(default)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_repo_root(explicit_repo_root: str | None) -> Path:
    if explicit_repo_root:
        return Path(explicit_repo_root).resolve()
    env_repo_root = os.environ.get("REPO_ROOT")
    if env_repo_root:
        return Path(env_repo_root).resolve()

    cwd = Path.cwd().resolve()
    if (cwd / "prd.json").exists() and (cwd / ".ai").exists():
        return cwd

    return Path(__file__).resolve().parents[2]


def state_dir(repo_root: Path) -> Path:
    return repo_root / ".ai" / "dropbox" / "state"


def watcher_state_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "watcher_state.json"


def watcher_latest_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / "watcher_latest.json"


def watcher_lock_path(repo_root: Path) -> Path:
    return state_dir(repo_root) / LOCK_FILENAME


def watcher_config_path(repo_root: Path) -> Path:
    return repo_root / ".ai" / "swarm" / "watcher.yaml"


def watcher_template_path(repo_root: Path) -> Path:
    return repo_root / ".ai" / "templates" / "watcher.md"


def watcher_report_root(repo_root: Path) -> Path:
    return repo_root / "data" / "reports" / "watcher"


def watcher_archive_root(repo_root: Path) -> Path:
    return repo_root / "data" / "archive" / "ai_dropbox"


def watcher_sandbox_root(repo_root: Path) -> Path:
    return repo_root / "data" / "tmp" / "watcher_sandboxes"


def normalize_state(doc: dict[str, Any]) -> dict[str, Any]:
    state = {
        "updated_at": "",
        "mailbox": {
            "offset": 0,
            "latest_ts": "",
            "events_seen": 0,
        },
        "watch_hashes": {},
        "seen_paper_cycles": [],
        "last_truth_drift_signature": "",
        "latest_packets": [],
        "ai_audit": {
            "last_inventory_packet_id": "",
            "last_archive_manifest": "",
        },
    }
    if isinstance(doc, dict):
        state.update(doc)

    mailbox = state.get("mailbox")
    if not isinstance(mailbox, dict):
        mailbox = {}
    state["mailbox"] = {
        "offset": int(mailbox.get("offset", 0) or 0),
        "latest_ts": str(mailbox.get("latest_ts") or ""),
        "events_seen": int(mailbox.get("events_seen", 0) or 0),
    }

    if not isinstance(state.get("watch_hashes"), dict):
        state["watch_hashes"] = {}
    state["watch_hashes"] = {
        str(key): str(value) for key, value in state["watch_hashes"].items()
    }

    if not isinstance(state.get("seen_paper_cycles"), list):
        state["seen_paper_cycles"] = []
    state["seen_paper_cycles"] = [str(item) for item in state["seen_paper_cycles"]]

    latest_packets = state.get("latest_packets")
    if not isinstance(latest_packets, list):
        latest_packets = []
    state["latest_packets"] = [item for item in latest_packets if isinstance(item, dict)][-10:]

    ai_audit = state.get("ai_audit")
    if not isinstance(ai_audit, dict):
        ai_audit = {}
    state["ai_audit"] = {
        "last_inventory_packet_id": str(ai_audit.get("last_inventory_packet_id") or ""),
        "last_archive_manifest": str(ai_audit.get("last_archive_manifest") or ""),
    }

    state["updated_at"] = str(state.get("updated_at") or "")
    state["last_truth_drift_signature"] = str(state.get("last_truth_drift_signature") or "")
    return state


def load_state(repo_root: Path) -> dict[str, Any]:
    return normalize_state(read_json(watcher_state_path(repo_root), {}))


def write_state(repo_root: Path, state: dict[str, Any]) -> None:
    normalized = normalize_state(state)
    normalized["updated_at"] = utc_now()
    atomic_write_json(watcher_state_path(repo_root), normalized)


class WatcherLockedError(RuntimeError):
    pass


@dataclass
class ProcessLock:
    path: Path
    handle: Any
    metadata: dict[str, Any]


@contextlib.contextmanager
def process_lock(repo_root: Path, mode: str) -> Iterator[ProcessLock]:
    state_root = state_dir(repo_root)
    state_root.mkdir(parents=True, exist_ok=True)
    lock_path = watcher_lock_path(repo_root)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise WatcherLockedError(f"watcher lock is already held: {lock_path}") from exc

        metadata = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "mode": mode,
            "repo_root": str(repo_root),
            "started_at": utc_now(),
        }
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps(metadata, indent=2) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
        yield ProcessLock(path=lock_path, handle=handle, metadata=metadata)
    finally:
        try:
            handle.seek(0)
            handle.truncate()
            handle.flush()
            os.fsync(handle.fileno())
        except OSError:
            pass
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def read_lock_metadata(repo_root: Path) -> dict[str, Any] | None:
    path = watcher_lock_path(repo_root)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing watcher config: {path}")
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise RuntimeError(f"Watcher config must decode to a mapping: {path}")
    return doc


def read_mailbox_delta(repo_root: Path, state: dict[str, Any]) -> dict[str, Any]:
    mailbox_path = state_dir(repo_root) / "mailbox.jsonl"
    mailbox_state = dict(state.get("mailbox") or {})
    offset = int(mailbox_state.get("offset", 0) or 0)
    latest_ts = str(mailbox_state.get("latest_ts") or "")
    events_seen = int(mailbox_state.get("events_seen", 0) or 0)

    if not mailbox_path.exists():
        return {
            "offset": 0,
            "latest_ts": latest_ts,
            "events_seen": events_seen,
            "new_events": 0,
        }

    file_size = mailbox_path.stat().st_size
    if offset > file_size:
        offset = 0

    new_events = 0
    with mailbox_path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        for raw in handle:
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                doc = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            new_events += 1
            events_seen += 1
            latest_ts = str(doc.get("ts") or latest_ts)
        offset = handle.tell()

    return {
        "offset": offset,
        "latest_ts": latest_ts,
        "events_seen": events_seen,
        "new_events": new_events,
    }


def read_story_claim(path: Path, *keys: str) -> str:
    doc = read_json(path, {})
    if not isinstance(doc, dict):
        return ""
    value: Any = doc
    for key in keys:
        if not isinstance(value, dict):
            return ""
        value = value.get(key)
    return str(value or "")


def compute_truth_context(repo_root: Path) -> dict[str, Any]:
    prd = read_json(repo_root / "prd.json", {})
    if not isinstance(prd, dict):
        prd = {}
    canonical_story_id = str(prd.get("activeStoryId") or "")

    docs_truth_path = state_dir(repo_root) / "docs_truth_receipt.json"
    story_promotion_path = state_dir(repo_root) / "story_promotion_receipt.json"
    lane_health_path = state_dir(repo_root) / "lane_health.json"
    finder_state_path = state_dir(repo_root) / "finder_state.json"
    finder_decision_path = state_dir(repo_root) / "finder_decision.json"
    mailbox_current_path = state_dir(repo_root) / "mailbox_current.json"

    story_claims = {
        "prd.json": canonical_story_id,
        "docs_truth_receipt.json": read_story_claim(docs_truth_path, "story_id"),
        "story_promotion_receipt.json": read_story_claim(story_promotion_path, "story_id"),
        "lane_health.json": read_story_claim(lane_health_path, "activeStoryId"),
        "mailbox_current.json": "",
        "finder_state.json": "",
        "finder_decision.json": "",
    }

    supporting_mismatches = {
        source: story_id
        for source, story_id in story_claims.items()
        if source != "prd.json" and story_id and story_id != canonical_story_id
    }
    consistency_status = "clean" if not supporting_mismatches else "truth_drift"
    signature_input = json.dumps(
        {
            "canonical_story_id": canonical_story_id,
            "supporting_mismatches": supporting_mismatches,
            "docs_truth_hash": sha256_file(docs_truth_path) if docs_truth_path.exists() else "",
            "story_promotion_hash": (
                sha256_file(story_promotion_path) if story_promotion_path.exists() else ""
            ),
            "lane_health_hash": sha256_file(lane_health_path) if lane_health_path.exists() else "",
        },
        sort_keys=True,
    ).encode("utf-8")
    signature = hashlib.sha256(signature_input).hexdigest()

    return {
        "canonical_story_id": canonical_story_id,
        "story_claims": story_claims,
        "supporting_mismatches": supporting_mismatches,
        "consistency_status": consistency_status,
        "truth_drift_signature": signature,
        "observed_inputs": [
            str(repo_root / "prd.json"),
            str(docs_truth_path),
            str(story_promotion_path),
            str(lane_health_path),
            str(mailbox_current_path),
            str(finder_state_path),
            str(finder_decision_path),
        ],
    }


def load_story_state(repo_root: Path) -> tuple[set[str], set[str], set[str]]:
    prd = read_json(repo_root / "prd.json", {})
    if not isinstance(prd, dict):
        return set(), set(), set()

    done: set[str] = set()
    active_or_deferred: set[str] = set()
    all_story_ids: set[str] = set()
    for story in prd.get("userStories", []):
        if not isinstance(story, dict):
            continue
        story_id = str(story.get("id") or "")
        if not story_id:
            continue
        all_story_ids.add(story_id)
        story_state = str(story.get("state") or "")
        if story_state == "done":
            done.add(story_id)
        if story_state in {"active", "ready", "recovery", "deferred"}:
            active_or_deferred.add(story_id)
    active_story_id = str(prd.get("activeStoryId") or "")
    if active_story_id:
        active_or_deferred.add(active_story_id)
        all_story_ids.add(active_story_id)
    return done, active_or_deferred, all_story_ids


def keep_control_plane_paths(repo_root: Path) -> set[Path]:
    root = state_dir(repo_root)
    return {
        root / "lane_health.md",
        root / "lane_health.json",
        root / "mailbox.jsonl",
        root / "mailbox_current.json",
        root / "finder_state.json",
        root / "finder_decision.json",
        root / "docs_truth_receipt.json",
        root / "docs_sync_status.json",
        root / "story_promotion_receipt.json",
        root / "research_proposal_review_receipt.json",
        root / "accepted_loops.md",
        root / "open_questions.md",
        root / "rejections.md",
        root / "watcher_state.json",
        root / "watcher_latest.json",
        root / LOCK_FILENAME,
    }


def path_story_id(path: Path) -> str:
    stem = path.name
    if "__" not in stem:
        return ""
    return stem.split("__", 1)[0]


def relative_path(path: Path, repo_root: Path) -> str:
    return str(path.resolve().relative_to(repo_root.resolve()))


def classify_dropbox_path(
    path: Path,
    repo_root: Path,
    done_story_ids: set[str],
    active_or_deferred_story_ids: set[str],
    newest_receipt_per_story: dict[str, Path],
) -> tuple[str, str]:
    rel = relative_path(path, repo_root)
    if path in keep_control_plane_paths(repo_root):
        return "keep_control_plane", "live control-plane receipt"

    if path.name == ".gitkeep":
        return "keep_control_plane", "tracked directory placeholder"

    story_id = path_story_id(path)
    if rel.startswith(".ai/dropbox/state/accepted_receipts/"):
        if not story_id:
            return "archive_ignored", "unscoped accepted receipt residue"
        if newest_receipt_per_story.get(story_id) == path:
            return "keep_control_plane", "newest accepted receipt for story"
        return "archive_ignored", "older duplicate accepted receipt"

    if rel.startswith(".ai/dropbox/state/runtime/"):
        if path.name.startswith("persistent_cycle_"):
            return "keep_control_plane", "current persistent-cycle runtime marker"
        return "keep_control_plane", "current runtime marker"

    if story_id in active_or_deferred_story_ids:
        return "keep_control_plane", "active or deferred story exchange surface"

    if story_id in done_story_ids:
        return "archive_ignored", "completed story exchange residue"

    if story_id in {"completion_audit", "no-active-story"}:
        return "archive_ignored", "completion or idle exchange residue"

    return "archive_ignored", "untracked dropbox exchange residue"


def classify_ai_file(
    path: Path,
    repo_root: Path,
    done_story_ids: set[str],
    active_or_deferred_story_ids: set[str],
    newest_receipt_per_story: dict[str, Path],
) -> tuple[str, str]:
    rel = relative_path(path, repo_root)
    if rel == ".ai/dropbox/README.md":
        return "keep_policy", "dropbox exchange doctrine surface"
    if rel.startswith(".ai/dropbox/"):
        return classify_dropbox_path(
            path=path,
            repo_root=repo_root,
            done_story_ids=done_story_ids,
            active_or_deferred_story_ids=active_or_deferred_story_ids,
            newest_receipt_per_story=newest_receipt_per_story,
        )
    if rel == ".ai/agents/README.md":
        return "delete_candidate", "redundant lane guide index with no repo consumers"
    if rel.startswith(".ai/templates/"):
        return "keep_template", "prompt or packet template"
    if rel.startswith(".ai/swarm/"):
        return "keep_policy", "machine-readable governance surface"
    if rel in {".ai/README.md", ".ai/index/current_repo_map.md"}:
        return "keep_policy", "repo-local doctrine or orientation surface"
    if rel.startswith(".ai/agents/"):
        return "keep_policy", "lane doctrine surface"
    return "keep_policy", "tracked repo-local AI support surface"


def copy_files_to_archive(
    repo_root: Path,
    packet_id: str,
    archive_candidates: list[Path],
) -> str:
    archive_root = watcher_archive_root(repo_root) / utc_stamp()
    files_root = archive_root / "files"
    manifest: dict[str, Any] = {
        "packet_id": packet_id,
        "created_at": utc_now(),
        "repo_root": str(repo_root),
        "copied_files": [],
    }

    for source in archive_candidates:
        target = files_root / source.relative_to(repo_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest["copied_files"].append(str(source.relative_to(repo_root)))

    manifest_path = archive_root / "manifest.json"
    atomic_write_json(manifest_path, manifest)
    return str(manifest_path)


def render_prompt(template_path: Path, replacements: dict[str, str]) -> str:
    template = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def write_packet(
    repo_root: Path,
    trigger_type: str,
    identifier: str,
    summary: dict[str, Any],
    prompt_replacements: dict[str, str],
    dry_run: bool,
) -> Path | None:
    packet_id = f"{trigger_type}__{identifier}__{utc_stamp()}"
    summary["packet_id"] = packet_id
    packet_dir = watcher_report_root(repo_root) / trigger_type / packet_id
    prompt_path = packet_dir / "prompt.md"
    review_path = packet_dir / "review.qmd"
    summary_path = packet_dir / "summary.json"

    summary["packet_dir"] = str(packet_dir)
    prompt_replacements = dict(prompt_replacements)
    prompt_replacements.setdefault("PACKET_ID", packet_id)
    prompt_replacements.setdefault("PACKET_DIR", str(packet_dir))
    prompt_replacements.setdefault("REPO_ROOT", str(repo_root))
    prompt_replacements.setdefault("SUMMARY_JSON", json.dumps(summary, indent=2, sort_keys=True))

    if dry_run:
        print(json.dumps(summary, indent=2))
        return None

    packet_dir.mkdir(parents=True, exist_ok=True)
    prompt_body = render_prompt(watcher_template_path(repo_root), prompt_replacements)
    atomic_write_text(prompt_path, prompt_body)
    atomic_write_json(summary_path, summary)
    review_qmd = build_review_qmd(summary, prompt_path)
    atomic_write_text(review_path, review_qmd)
    return packet_dir


def build_review_qmd(summary: dict[str, Any], prompt_path: Path) -> str:
    return textwrap.dedent(
        f"""\
        ---
        title: "Watcher Review: {summary['trigger_type']}"
        format: gfm
        ---

        ## Packet

        - packet_id: `{summary['packet_id']}`
        - advisory_only: `{summary['advisory_only']}`
        - trigger_type: `{summary['trigger_type']}`
        - canonical_story_id: `{summary['canonical_story_id'] or "none"}`
        - consistency_status: `{summary['consistency_status']}`
        - recommended_route: `{summary['recommended_route']}`
        - sandbox_used: `{summary['sandbox_used']}`
        - prompt_path: `{prompt_path}`

        ## Observed Inputs

        {chr(10).join(f"- `{item}`" for item in summary['observed_inputs'])}

        ## Findings

        {chr(10).join(f"- {item}" for item in summary['findings'])}

        ## Recommended Targets

        {chr(10).join(f"- `{item}`" for item in summary['recommended_targets'])}

        ## Open Risks

        {chr(10).join(f"- {item}" for item in summary['open_risks'])}

        ## Commands

        ```json
        {json.dumps(summary['commands_run'], indent=2)}
        ```
        """
    )


@dataclass
class SandboxContext:
    root: Path
    repo_root: Path
    env: dict[str, str]


@contextlib.contextmanager
def sandbox_context(repo_root: Path, packet_id: str) -> Iterator[SandboxContext]:
    sandbox_root = watcher_sandbox_root(repo_root) / packet_id
    if sandbox_root.exists():
        shutil.rmtree(sandbox_root)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    sandbox_repo_root = sandbox_root / "repo"

    ignore = shutil.ignore_patterns(
        ".git",
        "data",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "graphify-out",
        ".venv",
        "venv",
        "build",
        "dist",
    )
    shutil.copytree(repo_root, sandbox_repo_root, ignore=ignore, dirs_exist_ok=True)

    sandbox_data_dir = sandbox_repo_root / "data"
    sandbox_db_dir = sandbox_data_dir / "db"
    sandbox_db_dir.mkdir(parents=True, exist_ok=True)

    source_db = repo_root / "data" / "db" / "d5.db"
    source_duckdb = repo_root / "data" / "db" / "d5_analytics.duckdb"
    source_coinbase_raw = repo_root / "data" / "db" / "coinbase_raw.db"

    if source_db.exists():
        shutil.copy2(source_db, sandbox_db_dir / "d5.db")
    if source_duckdb.exists():
        shutil.copy2(source_duckdb, sandbox_db_dir / "d5_analytics.duckdb")
    if source_coinbase_raw.exists():
        shutil.copy2(source_coinbase_raw, sandbox_db_dir / "coinbase_raw.db")

    env = os.environ.copy()
    env["REPO_ROOT"] = str(sandbox_repo_root)
    env["DATA_DIR"] = str(sandbox_data_dir)
    env["DB_PATH"] = str(sandbox_db_dir / "d5.db")
    env["DUCKDB_PATH"] = str(sandbox_db_dir / "d5_analytics.duckdb")
    env["COINBASE_RAW_DB_PATH"] = str(sandbox_db_dir / "coinbase_raw.db")
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        str(sandbox_repo_root / "src")
        if not existing_pythonpath
        else f"{sandbox_repo_root / 'src'}:{existing_pythonpath}"
    )

    try:
        yield SandboxContext(root=sandbox_root, repo_root=sandbox_repo_root, env=env)
    finally:
        shutil.rmtree(sandbox_root, ignore_errors=True)


def expand_eval_command(command_text: str) -> list[str]:
    stripped = command_text.strip()
    if stripped == "d5 status":
        if shutil.which("d5"):
            return ["d5", "status"]
        return [sys.executable, "-m", "d5_trading_engine.cli", "status"]
    if stripped == "d5 run-label-program canonical-direction-v1":
        if shutil.which("d5"):
            return ["d5", "run-label-program", "canonical-direction-v1"]
        return [
            sys.executable,
            "-m",
            "d5_trading_engine.cli",
            "run-label-program",
            "canonical-direction-v1",
        ]
    if stripped == "d5 run-strategy-eval governed-challengers-v1":
        if shutil.which("d5"):
            return ["d5", "run-strategy-eval", "governed-challengers-v1"]
        return [
            sys.executable,
            "-m",
            "d5_trading_engine.cli",
            "run-strategy-eval",
            "governed-challengers-v1",
        ]
    if stripped.startswith("d5 run-paper-cycle "):
        parts = stripped.split()
        if shutil.which("d5"):
            return parts
        return [sys.executable, "-m", "d5_trading_engine.cli", *parts[1:]]
    raise RuntimeError(f"Watcher eval command is not allowlisted: {command_text}")


def run_sandbox_commands(
    repo_root: Path,
    packet_id: str,
    commands: list[str],
) -> list[dict[str, Any]]:
    if not commands:
        return []
    command_results: list[dict[str, Any]] = []
    with sandbox_context(repo_root=repo_root, packet_id=packet_id) as sandbox:
        for command_text in commands:
            argv = expand_eval_command(command_text)
            completed = subprocess.run(
                argv,
                cwd=sandbox.repo_root,
                env=sandbox.env,
                text=True,
                capture_output=True,
            )
            command_results.append(
                {
                    "command": command_text,
                    "argv": argv,
                    "exit_code": completed.returncode,
                    "stdout": completed.stdout.strip(),
                    "stderr": completed.stderr.strip(),
                    "sandbox_repo_root": str(sandbox.repo_root),
                    "sandbox_db_path": sandbox.env["DB_PATH"],
                    "sandbox_data_dir": sandbox.env["DATA_DIR"],
                }
            )
    return command_results


def should_run_sandbox(args: argparse.Namespace, commands: list[str]) -> bool:
    return bool(args.sandbox_evals and commands)


def packet_summary(
    trigger_type: str,
    canonical_story_id: str,
    observed_inputs: list[str],
    findings: list[str],
    recommended_route: str,
    recommended_targets: list[str],
    consistency_status: str,
    sandbox_used: bool,
    commands_run: list[dict[str, Any]] | None = None,
    open_risks: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "trigger_type": trigger_type,
        "advisory_only": True,
        "canonical_story_id": canonical_story_id,
        "observed_inputs": observed_inputs,
        "findings": findings,
        "recommended_route": recommended_route,
        "recommended_targets": recommended_targets,
        "consistency_status": consistency_status,
        "sandbox_used": sandbox_used,
        "commands_run": commands_run or [],
        "open_risks": open_risks or [],
    }


def maybe_record_packet(state: dict[str, Any], packet_dir: Path | None, summary: dict[str, Any]) -> None:
    if packet_dir is None:
        return
    latest_packets = list(state.get("latest_packets") or [])
    latest_packets.append(
        {
            "packet_id": summary["packet_id"],
            "trigger_type": summary["trigger_type"],
            "packet_dir": str(packet_dir),
            "created_at": utc_now(),
        }
    )
    state["latest_packets"] = latest_packets[-10:]


def maybe_emit_truth_drift(
    repo_root: Path,
    state: dict[str, Any],
    truth_context: dict[str, Any],
    dry_run: bool,
) -> tuple[bool, dict[str, Any]]:
    if truth_context["consistency_status"] != "truth_drift":
        state["last_truth_drift_signature"] = ""
        return False, state

    signature = truth_context["truth_drift_signature"]
    if state.get("last_truth_drift_signature") == signature:
        return True, state

    findings = [
        f"`prd.json` is canonical with activeStoryId `{truth_context['canonical_story_id'] or 'none'}`.",
        "Supporting state receipts disagree with the canonical story and must not drive watcher routing.",
    ]
    findings.extend(
        f"`{source}` claims `{story_id}`."
        for source, story_id in sorted(truth_context["supporting_mismatches"].items())
    )
    summary = packet_summary(
        trigger_type="truth_drift",
        canonical_story_id=truth_context["canonical_story_id"],
        observed_inputs=truth_context["observed_inputs"],
        findings=findings,
        recommended_route="issue",
        recommended_targets=["docs/issues/", "docs/handoff/", ".ai/dropbox/state/"],
        consistency_status="truth_drift",
        sandbox_used=False,
        open_risks=[
            "Watcher routing is blocked until the state receipts are monotonic with prd.json.",
        ],
    )
    packet_dir = write_packet(
        repo_root=repo_root,
        trigger_type="truth_drift",
        identifier=truth_context["canonical_story_id"] or "none",
        summary=summary,
        prompt_replacements={
            "TRIGGER_TYPE": "truth_drift",
            "CANONICAL_STORY_ID": truth_context["canonical_story_id"] or "none",
            "OBSERVED_INPUTS_JSON": json.dumps(truth_context["story_claims"], indent=2, sort_keys=True),
            "FINDINGS_BULLETS": "\n".join(f"- {item}" for item in findings),
            "RECOMMENDED_ROUTE": "docs/issues/",
        },
        dry_run=dry_run,
    )
    maybe_record_packet(state, packet_dir, summary)
    state["last_truth_drift_signature"] = signature
    return True, state


def maybe_emit_story_promotion_packet(
    repo_root: Path,
    state: dict[str, Any],
    truth_context: dict[str, Any],
    watcher_config: dict[str, Any],
    args: argparse.Namespace,
    dry_run: bool,
) -> dict[str, Any]:
    docs_truth_path = state_dir(repo_root) / "docs_truth_receipt.json"
    story_promotion_path = state_dir(repo_root) / "story_promotion_receipt.json"
    if not docs_truth_path.exists() and not story_promotion_path.exists():
        return state
    docs_hash = sha256_file(docs_truth_path) if docs_truth_path.exists() else ""
    promotion_hash = sha256_file(story_promotion_path) if story_promotion_path.exists() else ""
    signature = json.dumps(
        {
            "canonical_story_id": truth_context["canonical_story_id"],
            "docs_hash": docs_hash,
            "promotion_hash": promotion_hash,
        },
        sort_keys=True,
    )

    watch_hashes = dict(state.get("watch_hashes") or {})
    if watch_hashes.get("story_promotion_bundle") == signature:
        return state

    findings = [
        "Story promotion or docs-truth receipts changed under the canonical watcher watch surface.",
        f"Canonical story remains `{truth_context['canonical_story_id'] or 'none'}`.",
    ]
    commands_run: list[dict[str, Any]] = []
    if should_run_sandbox(
        args,
        watcher_config.get("triggers", {})
        .get("story_promotion_changed", {})
        .get("sandbox_eval_commands", []),
    ):
        packet_id = f"story_promotion_changed__{truth_context['canonical_story_id'] or 'none'}__{utc_stamp()}"
        commands_run = run_sandbox_commands(
            repo_root=repo_root,
            packet_id=packet_id,
            commands=watcher_config["triggers"]["story_promotion_changed"]["sandbox_eval_commands"],
        )

    summary = packet_summary(
        trigger_type="story_promotion_changed",
        canonical_story_id=truth_context["canonical_story_id"],
        observed_inputs=[str(docs_truth_path), str(story_promotion_path)],
        findings=findings,
        recommended_route="plan",
        recommended_targets=["docs/plans/", "docs/issues/", "prd.json"],
        consistency_status="clean",
        sandbox_used=bool(commands_run),
        commands_run=commands_run,
        open_risks=[
            "The watcher may recommend routing only; writer-integrator still owns canonical promotion decisions.",
        ],
    )
    packet_dir = write_packet(
        repo_root=repo_root,
        trigger_type="story_promotion_changed",
        identifier=truth_context["canonical_story_id"] or "none",
        summary=summary,
        prompt_replacements={
            "TRIGGER_TYPE": "story_promotion_changed",
            "CANONICAL_STORY_ID": truth_context["canonical_story_id"] or "none",
            "OBSERVED_INPUTS_JSON": json.dumps(
                {
                    "docs_truth_receipt": str(docs_truth_path),
                    "story_promotion_receipt": str(story_promotion_path),
                },
                indent=2,
                sort_keys=True,
            ),
            "FINDINGS_BULLETS": "\n".join(f"- {item}" for item in findings),
            "RECOMMENDED_ROUTE": "docs/plans/",
        },
        dry_run=dry_run,
    )
    maybe_record_packet(state, packet_dir, summary)
    watch_hashes["story_promotion_bundle"] = signature
    state["watch_hashes"] = watch_hashes
    return state


def maybe_emit_strategy_report_packet(
    repo_root: Path,
    state: dict[str, Any],
    truth_context: dict[str, Any],
    watcher_config: dict[str, Any],
    args: argparse.Namespace,
    dry_run: bool,
) -> dict[str, Any]:
    report_path = repo_root / ".ai" / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json"
    if not report_path.exists():
        return state

    report_hash = sha256_file(report_path)
    watch_hashes = dict(state.get("watch_hashes") or {})
    if watch_hashes.get("strategy_report") == report_hash:
        return state

    report_doc = read_json(report_path, {})
    top_family = str(report_doc.get("top_family") or "none")
    run_id = str(report_doc.get("run_id") or top_family or "strategy")
    findings = [
        f"Strategy challenger report changed with top family `{top_family}`.",
        "The watcher remains advisory and may only route follow-on work or bounded sandbox checks.",
    ]
    commands_run: list[dict[str, Any]] = []
    eval_commands = (
        watcher_config.get("triggers", {})
        .get("strategy_report_changed", {})
        .get("sandbox_eval_commands", [])
    )
    if should_run_sandbox(args, eval_commands):
        packet_id = f"strategy_report_changed__{run_id}__{utc_stamp()}"
        commands_run = run_sandbox_commands(
            repo_root=repo_root,
            packet_id=packet_id,
            commands=eval_commands,
        )

    summary = packet_summary(
        trigger_type="strategy_report_changed",
        canonical_story_id=truth_context["canonical_story_id"],
        observed_inputs=[str(report_path)],
        findings=findings,
        recommended_route="task",
        recommended_targets=["docs/task/", "docs/gaps/", ".ai/dropbox/research/"],
        consistency_status="clean",
        sandbox_used=bool(commands_run),
        commands_run=commands_run,
        open_risks=[
            "Strategy-family challengers remain advisory until promotion rules explicitly widen authority.",
        ],
    )
    packet_dir = write_packet(
        repo_root=repo_root,
        trigger_type="strategy_report_changed",
        identifier=run_id.replace("/", "_").replace(":", "_"),
        summary=summary,
        prompt_replacements={
            "TRIGGER_TYPE": "strategy_report_changed",
            "CANONICAL_STORY_ID": truth_context["canonical_story_id"] or "none",
            "OBSERVED_INPUTS_JSON": json.dumps(report_doc, indent=2, sort_keys=True),
            "FINDINGS_BULLETS": "\n".join(f"- {item}" for item in findings),
            "RECOMMENDED_ROUTE": "docs/task/",
        },
        dry_run=dry_run,
    )
    maybe_record_packet(state, packet_dir, summary)
    watch_hashes["strategy_report"] = report_hash
    state["watch_hashes"] = watch_hashes
    return state


def maybe_emit_paper_cycle_packets(
    repo_root: Path,
    state: dict[str, Any],
    truth_context: dict[str, Any],
    watcher_config: dict[str, Any],
    args: argparse.Namespace,
    dry_run: bool,
) -> dict[str, Any]:
    seen_cycles = set(str(item) for item in state.get("seen_paper_cycles") or [])
    cycle_root = repo_root / "data" / "paper_runtime" / "cycles"
    if not cycle_root.exists():
        return state

    eval_commands = (
        watcher_config.get("triggers", {})
        .get("paper_cycle_closed", {})
        .get("sandbox_eval_commands", [])
    )

    for summary_path in sorted(cycle_root.glob("*/cycle_summary.json")):
        cycle_doc = read_json(summary_path, {})
        session_key = str(cycle_doc.get("session_key") or summary_path.parent.name)
        if session_key in seen_cycles:
            continue
        report_qmd = summary_path.parent / "report.qmd"
        findings = [
            f"New paper-runtime cycle `{session_key}` was detected.",
            f"Filled={cycle_doc.get('filled')} status={cycle_doc.get('session_status')}.",
        ]
        commands_run: list[dict[str, Any]] = []
        if should_run_sandbox(args, eval_commands):
            packet_id = f"paper_cycle_closed__{session_key}__{utc_stamp()}"
            commands_run = run_sandbox_commands(
                repo_root=repo_root,
                packet_id=packet_id,
                commands=eval_commands,
            )

        summary = packet_summary(
            trigger_type="paper_cycle_closed",
            canonical_story_id=truth_context["canonical_story_id"],
            observed_inputs=[str(summary_path), str(report_qmd)],
            findings=findings,
            recommended_route="task",
            recommended_targets=["docs/task/", "docs/issues/", "data/paper_runtime/cycles/"],
            consistency_status="clean",
            sandbox_used=bool(commands_run),
            commands_run=commands_run,
            open_risks=[
                "Paper-cycle reviews remain advisory and must not widen into live trading or wallet automation.",
            ],
        )
        packet_dir = write_packet(
            repo_root=repo_root,
            trigger_type="paper_cycle_closed",
            identifier=session_key.replace("/", "_").replace(":", "_"),
            summary=summary,
            prompt_replacements={
                "TRIGGER_TYPE": "paper_cycle_closed",
                "CANONICAL_STORY_ID": truth_context["canonical_story_id"] or "none",
                "OBSERVED_INPUTS_JSON": json.dumps(cycle_doc, indent=2, sort_keys=True),
                "FINDINGS_BULLETS": "\n".join(f"- {item}" for item in findings),
                "RECOMMENDED_ROUTE": "docs/task/",
            },
            dry_run=dry_run,
        )
        maybe_record_packet(state, packet_dir, summary)
        seen_cycles.add(session_key)

    state["seen_paper_cycles"] = sorted(seen_cycles)
    return state


def audit_ai_surfaces(
    repo_root: Path,
    state: dict[str, Any],
    dry_run: bool,
) -> dict[str, Any]:
    done_story_ids, active_or_deferred_story_ids, _ = load_story_state(repo_root)

    accepted_receipts_dir = state_dir(repo_root) / "accepted_receipts"
    newest_receipt_per_story: dict[str, Path] = {}
    if accepted_receipts_dir.exists():
        for receipt_path in sorted(accepted_receipts_dir.glob("*.json")):
            story_id = path_story_id(receipt_path)
            if not story_id:
                continue
            current = newest_receipt_per_story.get(story_id)
            if current is None or receipt_path.stat().st_mtime >= current.stat().st_mtime:
                newest_receipt_per_story[story_id] = receipt_path

    inventory: list[dict[str, Any]] = []
    archive_candidates: list[Path] = []
    for path in sorted((repo_root / ".ai").rglob("*")):
        if not path.is_file():
            continue
        classification, reason = classify_ai_file(
            path=path,
            repo_root=repo_root,
            done_story_ids=done_story_ids,
            active_or_deferred_story_ids=active_or_deferred_story_ids,
            newest_receipt_per_story=newest_receipt_per_story,
        )
        entry = {
            "path": relative_path(path, repo_root),
            "classification": classification,
            "reason": reason,
        }
        inventory.append(entry)
        if classification == "archive_ignored":
            archive_candidates.append(path)

    packet_id = f"ai_hygiene__{utc_stamp()}"
    archive_manifest = ""
    if archive_candidates and not dry_run:
        archive_manifest = copy_files_to_archive(
            repo_root=repo_root,
            packet_id=packet_id,
            archive_candidates=archive_candidates,
        )

    findings = [
        "Tracked governance and template surfaces are preserved by default.",
        "Ignored `.ai/dropbox` exchange residue is classified separately from live control-plane receipts.",
        "Only `.ai/agents/README.md` is a tracked delete candidate in v1.",
    ]
    if archive_candidates:
        findings.append(
            f"Classified {len(archive_candidates)} ignored `.ai/dropbox` files as archive candidates."
        )

    summary = packet_summary(
        trigger_type="ai_hygiene",
        canonical_story_id=read_story_claim(repo_root / "prd.json", "activeStoryId"),
        observed_inputs=[str(repo_root / ".ai"), str(repo_root / "prd.json")],
        findings=findings,
        recommended_route="issue",
        recommended_targets=["docs/issues/", "docs/gaps/", ".ai/dropbox/"],
        consistency_status="clean",
        sandbox_used=False,
        commands_run=[],
        open_risks=[
            "Archive copy exists in data/archive only; ignored residue is not deleted automatically in v1.",
        ],
    )
    summary["archive_manifest"] = archive_manifest
    summary["inventory_count"] = len(inventory)

    packet_dir = write_packet(
        repo_root=repo_root,
        trigger_type="ai_hygiene",
        identifier="inventory",
        summary=summary,
        prompt_replacements={
            "TRIGGER_TYPE": "ai_hygiene",
            "CANONICAL_STORY_ID": summary["canonical_story_id"] or "none",
            "OBSERVED_INPUTS_JSON": json.dumps(inventory, indent=2, sort_keys=True),
            "FINDINGS_BULLETS": "\n".join(f"- {item}" for item in findings),
            "RECOMMENDED_ROUTE": "docs/issues/",
        },
        dry_run=dry_run,
    )
    if packet_dir is not None:
        atomic_write_json(packet_dir / "inventory.json", inventory)
    maybe_record_packet(state, packet_dir, summary)
    state["ai_audit"] = {
        "last_inventory_packet_id": summary["packet_id"],
        "last_archive_manifest": archive_manifest,
    }
    return state


def status_payload(repo_root: Path) -> dict[str, Any]:
    latest = read_json(watcher_latest_path(repo_root), {})
    state = load_state(repo_root)
    return {
        "repo_root": str(repo_root),
        "lock": read_lock_metadata(repo_root),
        "latest": latest,
        "state": {
            "updated_at": state.get("updated_at"),
            "mailbox": state.get("mailbox"),
            "last_truth_drift_signature": state.get("last_truth_drift_signature"),
            "latest_packets": state.get("latest_packets"),
            "ai_audit": state.get("ai_audit"),
        },
    }


def write_latest(repo_root: Path, state: dict[str, Any], truth_context: dict[str, Any]) -> None:
    payload = {
        "updated_at": utc_now(),
        "canonical_story_id": truth_context["canonical_story_id"],
        "consistency_status": truth_context["consistency_status"],
        "latest_packets": state.get("latest_packets", []),
        "mailbox": state.get("mailbox"),
        "ai_audit": state.get("ai_audit"),
    }
    atomic_write_json(watcher_latest_path(repo_root), payload)


def run_once(repo_root: Path, args: argparse.Namespace) -> int:
    watcher_config = load_yaml(watcher_config_path(repo_root))
    state = load_state(repo_root)
    state["mailbox"] = read_mailbox_delta(repo_root, state)
    truth_context = compute_truth_context(repo_root)

    if args.audit_ai:
        state = audit_ai_surfaces(repo_root=repo_root, state=state, dry_run=args.dry_run)

    blocked, state = maybe_emit_truth_drift(
        repo_root=repo_root,
        state=state,
        truth_context=truth_context,
        dry_run=args.dry_run,
    )

    if not blocked:
        state = maybe_emit_story_promotion_packet(
            repo_root=repo_root,
            state=state,
            truth_context=truth_context,
            watcher_config=watcher_config,
            args=args,
            dry_run=args.dry_run,
        )
        state = maybe_emit_strategy_report_packet(
            repo_root=repo_root,
            state=state,
            truth_context=truth_context,
            watcher_config=watcher_config,
            args=args,
            dry_run=args.dry_run,
        )
        state = maybe_emit_paper_cycle_packets(
            repo_root=repo_root,
            state=state,
            truth_context=truth_context,
            watcher_config=watcher_config,
            args=args,
            dry_run=args.dry_run,
        )

    if not args.dry_run:
        write_state(repo_root, state)
        write_latest(repo_root, state, truth_context)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repo-native advisory watcher for Defi-engine truth surfaces."
    )
    parser.add_argument("--repo", default=None, help="Repo root. Defaults to REPO_ROOT or cwd.")
    parser.add_argument("--once", action="store_true", help="Run one watcher pass.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help="Loop interval in seconds.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print packets but do not write.")
    parser.add_argument(
        "--sandbox-evals",
        action="store_true",
        help="Allow bounded sandbox eval commands defined in the watcher contract.",
    )
    parser.add_argument(
        "--audit-ai",
        action="store_true",
        help="Run the .ai hygiene inventory and archive-copy pass.",
    )
    parser.add_argument("--status", action="store_true", help="Print watcher status as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo_root = discover_repo_root(args.repo)

    if args.status:
        print(json.dumps(status_payload(repo_root), indent=2))
        return 0

    mode = "loop" if args.loop else "once"
    if not args.once and not args.loop:
        args.once = True

    try:
        with process_lock(repo_root, mode=mode):
            if args.loop:
                while True:
                    run_once(repo_root, args)
                    time.sleep(max(args.interval, 1))
            return run_once(repo_root, args)
    except WatcherLockedError as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_LOCKED


if __name__ == "__main__":
    raise SystemExit(main())
