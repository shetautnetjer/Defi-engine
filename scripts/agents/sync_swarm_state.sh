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

repo_root = Path(sys.argv[1])
prd_path = repo_root / "prd.json"
writer_audit_path = repo_root / ".ai" / "dropbox" / "state" / "completion_audit_writer.json"
finder_state_path = repo_root / ".ai" / "dropbox" / "state" / "finder_state.json"
lane_health_path = repo_root / ".ai" / "dropbox" / "state" / "lane_health.json"

doc = json.loads(prd_path.read_text())
stories = doc.get("userStories", [])
eligible_states = {"ready", "active", "recovery"}
eligible = [story for story in stories if story.get("state") in eligible_states]

writer_audit = {}
if writer_audit_path.exists():
    try:
        writer_audit = json.loads(writer_audit_path.read_text())
    except json.JSONDecodeError:
        writer_audit = {}

finder_state = {}
if finder_state_path.exists():
    try:
        finder_state = json.loads(finder_state_path.read_text())
    except json.JSONDecodeError:
        finder_state = {}

lane_health = {}
if lane_health_path.exists():
    try:
        lane_health = json.loads(lane_health_path.read_text())
    except json.JSONDecodeError:
        lane_health = {}

completion_status = "pending"
swarm_state = "active" if eligible else "backlog_exhausted"
writer_status = str(writer_audit.get("status") or "")
pending_trigger = finder_state.get("pendingTrigger")
last_completion_audit_id = str(writer_audit.get("audit_id") or "")
last_finder_audit_id = str(finder_state.get("lastFinderAuditId") or "")

if eligible:
    completion_status = "pending"
    swarm_state = "active"
else:
    running_audit = False
    for lane in lane_health.get("lanes", []):
        if lane.get("name") in {"architecture", "writer-integrator"} and lane.get("status") == "running":
            running_audit = True
            break

    if writer_status == "gap_promoted":
        completion_status = "gaps_promoted"
        swarm_state = "active" if any(story.get("state") in eligible_states for story in stories) else "audit_followons_present"
    elif writer_status in {"clean", "audit_known_only"} and not pending_trigger:
        completion_status = "clean"
        swarm_state = "terminal_complete"
    elif pending_trigger:
        completion_status = "running" if running_audit else "pending"
        swarm_state = "audit_followons_present"
    elif running_audit:
        completion_status = "running"
        swarm_state = "backlog_exhausted"
    else:
        completion_status = "pending"
        swarm_state = "backlog_exhausted"

doc["swarmState"] = swarm_state
doc["completionAuditState"] = completion_status
doc["lastCompletionAuditReceiptId"] = last_completion_audit_id
doc["lastFinderAuditId"] = last_finder_audit_id
prd_path.write_text(json.dumps(doc, indent=2) + "\n")
PY
