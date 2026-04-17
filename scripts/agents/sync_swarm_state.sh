#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: sync_swarm_state.sh [--repo PATH]

Refresh the top-level swarm completion fields in prd.json.
EOF
}

repo="${PWD}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'sync_swarm_state: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"

python - "$repo_root" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

repo_root = Path(sys.argv[1])
prd_path = repo_root / "prd.json"
writer_audit_path = repo_root / ".ai" / "dropbox" / "state" / "completion_audit_writer.json"
finder_state_path = repo_root / ".ai" / "dropbox" / "state" / "finder_state.json"
lane_health_path = repo_root / ".ai" / "dropbox" / "state" / "lane_health.json"

def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def write_json(path: Path, doc: dict[str, Any]) -> None:
    path.write_text(json.dumps(doc, indent=2) + "\n")


def normalize_writer_audit(path: Path) -> dict[str, Any]:
    audit = read_json(path, {})
    if not isinstance(audit, dict):
        return {}
    changed = False
    audited_at = str(audit.get("audited_at") or "")
    if audited_at and not audit.get("audit_id"):
        audit["audit_id"] = f"completion_audit_writer::{audited_at}"
        changed = True
    for key in ("promoted_story_ids", "deferred_story_ids", "rationale"):
        if not isinstance(audit.get(key), list):
            audit[key] = []
            changed = True
    if changed:
        write_json(path, audit)
    return audit


def lane_tracks_completion_scope(lane: dict[str, Any]) -> bool:
    scopes = {
        str(lane.get("currentScope") or ""),
        str(lane.get("activeScope") or ""),
        str(lane.get("lastLaunchScope") or ""),
        str(lane.get("lastCompletionScope") or ""),
    }
    return "completion_audit" in scopes


doc = json.loads(prd_path.read_text())
stories = doc.get("userStories", [])
eligible_states = {"ready", "active", "recovery"}
eligible = [story for story in stories if story.get("state") in eligible_states]
writer_audit = normalize_writer_audit(writer_audit_path) if writer_audit_path.exists() else {}
finder_state = read_json(finder_state_path, {})
lane_health = read_json(lane_health_path, {})
story_health = lane_health.get("story") if isinstance(lane_health, dict) else {}
lane_rows = lane_health.get("lanes") if isinstance(lane_health, dict) else []
if not isinstance(story_health, dict):
    story_health = {}
if not isinstance(lane_rows, list):
    lane_rows = []

completion_status = "pending"
swarm_state = "active" if eligible else "backlog_exhausted"
writer_status = str(writer_audit.get("status") or "")
pending_trigger = finder_state.get("pendingTrigger") if isinstance(finder_state, dict) else None
pending_scope = str((pending_trigger or {}).get("scope") or "")
last_completion_audit_id = str(writer_audit.get("audit_id") or "")
last_finder_audit_id = str((finder_state or {}).get("lastFinderAuditId") or "")
current_scope = str(story_health.get("currentScope") or "")
current_mode = str(story_health.get("currentMode") or "")
running_audit = any(
    isinstance(lane, dict)
    and lane.get("name") in {"research", "architecture", "writer-integrator"}
    and str(lane.get("status") or "") == "running"
    for lane in lane_rows
)
completion_scope_being_decided = current_scope == "completion_audit" and current_mode in {"finder", "completion_audit"}
completion_scope_unresolved = any(
    isinstance(lane, dict)
    and lane_tracks_completion_scope(lane)
    and str(lane.get("status") or "") in {"running", "stale", "failed", "blocked"}
    for lane in lane_rows
)
writer_audit_mismatch = bool(
    last_completion_audit_id
    and last_finder_audit_id
    and last_completion_audit_id != last_finder_audit_id
)

if eligible:
    completion_status = "pending"
    swarm_state = "active"
    if not doc.get("activeStoryId"):
        doc["activeStoryId"] = str(eligible[0].get("id") or "")
else:
    if writer_status == "gap_promoted":
        completion_status = "gaps_promoted"
        swarm_state = "active" if any(story.get("state") in eligible_states for story in stories) else "audit_followons_present"
    elif pending_trigger or completion_scope_being_decided or completion_scope_unresolved or writer_audit_mismatch:
        completion_status = "running" if running_audit or completion_scope_being_decided or completion_scope_unresolved else "pending"
        swarm_state = "audit_followons_present"
    elif writer_status in {"clean", "audit_known_only"}:
        completion_status = "clean"
        swarm_state = "terminal_complete"
    elif running_audit:
        completion_status = "running"
        swarm_state = "backlog_exhausted"
    else:
        completion_status = "pending"
        swarm_state = "backlog_exhausted"

    if swarm_state == "terminal_complete":
        doc["activeStoryId"] = ""

doc["swarmState"] = swarm_state
doc["completionAuditState"] = completion_status
doc["lastCompletionAuditReceiptId"] = last_completion_audit_id
doc["lastFinderAuditId"] = last_finder_audit_id
prd_path.write_text(json.dumps(doc, indent=2) + "\n")
PY
