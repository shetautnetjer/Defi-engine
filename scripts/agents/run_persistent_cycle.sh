#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: run_persistent_cycle.sh [--repo PATH] [--session NAME] [--interval SECONDS] [--max-cycles COUNT] [--iterations COUNT] [--start-if-missing]

Run a continuous completion loop for the Defi-engine four-lane swarm.
EOF
}

repo="${PWD}"
session_name=""
interval_seconds="60"
max_cycles="0"
start_if_missing="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    --session)
      session_name="${2:?--session requires a value}"
      shift 2
      ;;
    --interval)
      interval_seconds="${2:?--interval requires a value}"
      shift 2
      ;;
    --max-cycles)
      max_cycles="${2:?--max-cycles requires a value}"
      shift 2
      ;;
    --iterations)
      max_cycles="${2:?--iterations requires a value}"
      shift 2
      ;;
    --start-if-missing)
      start_if_missing="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'run_persistent_cycle: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
completion_architecture_prompt="$repo_root/.ai/templates/architecture_completion_audit.md"
completion_writer_prompt="$repo_root/.ai/templates/writer_completion_audit.md"
completion_architecture_json="$repo_root/.ai/dropbox/state/completion_audit_architecture.json"
completion_writer_json="$repo_root/.ai/dropbox/state/completion_audit_writer.json"
architecture_finder_prompt="$repo_root/.ai/templates/architecture_finder.md"
research_finder_prompt="$repo_root/.ai/templates/research_finder.md"
finder_state_json="$(defi_swarm_finder_state_path "$repo_root")"
finder_decision_json="$(defi_swarm_finder_decision_path "$repo_root")"
lane_health_json="$(defi_swarm_lane_health_json_path "$repo_root")"
mailbox_path="$(defi_swarm_mailbox_path "$repo_root")"
supervisor_launch_json="$(defi_swarm_supervisor_launch_path "$repo_root")"
supervisor_heartbeat_json="$(defi_swarm_supervisor_heartbeat_path "$repo_root")"
supervisor_last_exit_json="$(defi_swarm_supervisor_last_exit_path "$repo_root")"
run_mode="continuous"
if [[ "$max_cycles" != "0" ]]; then
  run_mode="bounded"
fi
exit_reason="running"
exit_signal=""

write_supervisor_launch() {
  jq -nc \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg repo "$repo_root" \
    --arg session "$session_name" \
    --argjson pid "$$" \
    --argjson interval "$interval_seconds" \
    --arg mode "$run_mode" \
    --argjson maxCycles "$max_cycles" \
    '{ts:$ts, repo:$repo, session:$session, pid:$pid, intervalSeconds:$interval, mode:$mode, maxCycles:$maxCycles}' > "$supervisor_launch_json"
}

write_supervisor_heartbeat() {
  local cycle="${1:?cycle required}"
  local active_story
  active_story="$(defi_swarm_active_story "$repo_root")"
  jq -nc \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg repo "$repo_root" \
    --arg session "$session_name" \
    --arg storyId "$active_story" \
    --arg mode "$run_mode" \
    --argjson pid "$$" \
    --argjson cycle "$cycle" \
    --argjson interval "$interval_seconds" \
    '{ts:$ts, repo:$repo, session:$session, pid:$pid, cycle:$cycle, intervalSeconds:$interval, mode:$mode, activeStoryId:$storyId}' > "$supervisor_heartbeat_json"
}

write_supervisor_last_exit() {
  local exit_code="${1:?exit code required}"
  jq -nc \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg repo "$repo_root" \
    --arg session "$session_name" \
    --arg reason "$exit_reason" \
    --arg signal "$exit_signal" \
    --arg mode "$run_mode" \
    --argjson pid "$$" \
    --argjson exitCode "$exit_code" \
    '{ts:$ts, repo:$repo, session:$session, pid:$pid, mode:$mode, exitCode:$exitCode, reason:$reason, signal:($signal | select(length > 0))}' > "$supervisor_last_exit_json"
}

on_signal() {
  local signal="${1:?signal required}"
  exit_reason="terminated"
  exit_signal="$signal"
  exit 143
}

on_exit() {
  local exit_code=$?
  write_supervisor_last_exit "$exit_code"
}

trap 'on_signal TERM' TERM
trap 'on_signal INT' INT
trap on_exit EXIT

sync_swarm_state() {
  "$script_dir/sync_swarm_state.sh" --repo "$repo_root" >/dev/null
}

ensure_session() {
  if tmux has-session -t "$session_name" >/dev/null 2>&1; then
    return 0
  fi
  if [[ "$start_if_missing" != "true" ]]; then
    printf 'persistent-cycle: session %s is not running and --start-if-missing was not provided\n' "$session_name" >&2
    return 1
  fi
  "$script_dir/start_swarm.sh" --repo "$repo_root" --session "$session_name" --launch-all >/dev/null
}

ensure_active_story() {
  local active_story current_state next_story
  active_story="$(defi_swarm_active_story "$repo_root")"

  if [[ -n "$active_story" && "$active_story" != "null" ]] && defi_swarm_story_is_eligible "$repo_root" "$active_story"; then
    current_state="$(defi_swarm_story_state "$repo_root" "$active_story")"
    if [[ "$current_state" == "ready" ]]; then
      "$script_dir/update_story_state.sh" --repo "$repo_root" --story-id "$active_story" --state active >/dev/null
    fi
    return 0
  fi

  next_story="$(defi_swarm_next_eligible_story "$repo_root")"
  if [[ -n "$next_story" ]]; then
    "$script_dir/update_story_state.sh" --repo "$repo_root" --story-id "$next_story" --state active >/dev/null
  fi
}

lane_status() {
  local lane_name="${1:?lane required}"
  jq -r --arg lane "$lane_name" '.lanes[] | select(.name == $lane) | .status' "$lane_health_json"
}

completion_audit_mode() {
  local latest_truth_epoch=0
  local arch_epoch=0
  local writer_epoch=0
  local writer_status=""

  if [[ -f "$repo_root/prd.json" ]]; then
    latest_truth_epoch="$(stat -c %Y "$repo_root/prd.json")"
  fi
  if [[ -f "$repo_root/progress.txt" ]]; then
    local progress_epoch
    progress_epoch="$(stat -c %Y "$repo_root/progress.txt")"
    if (( progress_epoch > latest_truth_epoch )); then
      latest_truth_epoch="$progress_epoch"
    fi
  fi
  if [[ -f "$completion_architecture_json" ]]; then
    arch_epoch="$(stat -c %Y "$completion_architecture_json")"
  fi
  if [[ -f "$completion_writer_json" ]]; then
    writer_epoch="$(stat -c %Y "$completion_writer_json")"
    writer_status="$(jq -r '.status // ""' "$completion_writer_json" 2>/dev/null || true)"
  fi

  if [[ "$(lane_status architecture)" == "running" ]]; then
    printf 'waiting_architecture\n'
    return 0
  fi
  if [[ "$(lane_status writer-integrator)" == "running" ]]; then
    printf 'waiting_writer\n'
    return 0
  fi
  if (( arch_epoch == 0 || arch_epoch < latest_truth_epoch )); then
    printf 'launch_architecture\n'
    return 0
  fi
  if (( writer_epoch == 0 || writer_epoch < arch_epoch )); then
    printf 'launch_writer\n'
    return 0
  fi
  case "$writer_status" in
    clean|audit_known_only)
      printf 'clean\n'
      return 0
      ;;
    gap_promoted)
      printf 'gaps_promoted\n'
      return 0
      ;;
  esac
  printf 'waiting_writer\n'
}

queue_receipt_followons() {
  python - "$repo_root" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
finder_state_path = repo_root / ".ai" / "dropbox" / "state" / "finder_state.json"
receipts_dir = repo_root / ".ai" / "dropbox" / "state" / "accepted_receipts"

state = json.loads(finder_state_path.read_text())
matches = sorted(receipts_dir.glob("*.json"))
if not matches:
    raise SystemExit(0)

latest_path = matches[-1]
latest = json.loads(latest_path.read_text())
receipt_id = str(latest.get("receipt_id") or "")
if not receipt_id or state.get("lastProcessedReceiptId") == receipt_id:
    raise SystemExit(0)

queued = list(state.get("queuedReceiptFollowons") or [])
needs_followon = any(
    latest.get(key)
    for key in ("contradictions_found", "unresolved_risks", "promotion_targets")
)
if needs_followon and all(item.get("receiptId") != receipt_id for item in queued):
    queued.append(
        {
            "receiptId": receipt_id,
            "storyId": str(latest.get("story_id") or ""),
            "queuedAt": str(latest.get("timestamp") or ""),
        }
    )
state["queuedReceiptFollowons"] = queued
state["lastProcessedReceiptId"] = receipt_id
finder_state_path.write_text(json.dumps(state, indent=2) + "\n")
PY
}

queue_repeated_failure_trigger() {
  python - "$repo_root" "$mailbox_path" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
mailbox_path = Path(sys.argv[2])
finder_state_path = repo_root / ".ai" / "dropbox" / "state" / "finder_state.json"
state = json.loads(finder_state_path.read_text())
if state.get("pendingTrigger"):
    raise SystemExit(0)

events = []
for raw in mailbox_path.read_text().splitlines():
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
    raise SystemExit(0)

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
    raise SystemExit(0)
if state.get("lastProcessedFailureSignature") == signature:
    raise SystemExit(0)

state["pendingTrigger"] = {
    "triggerId": f"finder::{last.get('ts','')}::{last.get('storyId','')}",
    "triggerType": "repeated_failure",
    "scope": str(last.get("storyId") or ""),
    "storyId": str(last.get("storyId") or ""),
    "failureSignature": signature,
    "createdAt": str(last.get("ts") or ""),
}
state["lastProcessedFailureSignature"] = signature
finder_state_path.write_text(json.dumps(state, indent=2) + "\n")
PY
}

queue_completion_trigger() {
  python - "$repo_root" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
finder_state_path = repo_root / ".ai" / "dropbox" / "state" / "finder_state.json"
receipts_dir = repo_root / ".ai" / "dropbox" / "state" / "accepted_receipts"
prd = json.loads((repo_root / "prd.json").read_text())
eligible_states = {"ready", "active", "recovery"}
if any(story.get("state") in eligible_states for story in prd.get("userStories", [])):
    raise SystemExit(0)

state = json.loads(finder_state_path.read_text())
if state.get("pendingTrigger"):
    raise SystemExit(0)

latest_receipt = ""
matches = sorted(receipts_dir.glob("*.json"))
if matches:
    latest = json.loads(matches[-1].read_text())
    latest_receipt = str(latest.get("receipt_id") or "")

scope_signature = f"completion_audit::{latest_receipt}"
if state.get("lastProcessedCompletionScope") == scope_signature:
    raise SystemExit(0)

state["pendingTrigger"] = {
    "triggerId": scope_signature,
    "triggerType": "completion_audit",
    "scope": "completion_audit",
    "storyId": str(prd.get("activeStoryId") or ""),
    "sourceReceiptId": latest_receipt,
    "createdAt": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
}
finder_state_path.write_text(json.dumps(state, indent=2) + "\n")
PY
}

finder_phase() {
  python - "$repo_root" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
state_dir = repo_root / ".ai" / "dropbox" / "state"
finder_state = json.loads((state_dir / "finder_state.json").read_text())
pending = finder_state.get("pendingTrigger")
if not pending:
    print("none")
    raise SystemExit(0)

scope = str(pending.get("scope") or "")
if not scope:
    print("malformed")
    raise SystemExit(0)

created = str(pending.get("createdAt") or "")
decision_path = state_dir / "finder_decision.json"
completion_writer_path = state_dir / "completion_audit_writer.json"
arch_files = [
    repo_root / ".ai" / "dropbox" / "architecture" / f"{scope}__architecture_efficiency_audit.md",
    repo_root / ".ai" / "dropbox" / "architecture" / f"{scope}__subtraction_candidates.json",
    repo_root / ".ai" / "dropbox" / "architecture" / f"{scope}__followon_story_candidates.json",
]
research_files = [
    repo_root / ".ai" / "dropbox" / "research" / f"{scope}__research_gap_scan.md",
    repo_root / ".ai" / "dropbox" / "research" / f"{scope}__unknowns_and_needed_evidence.json",
    repo_root / ".ai" / "dropbox" / "research" / f"{scope}__followon_story_candidates.json",
]

def ready(paths: list[Path]) -> bool:
    return all(path.exists() for path in paths)

if not ready(arch_files):
    print("launch_architecture")
    raise SystemExit(0)
if not ready(research_files):
    print("launch_research")
    raise SystemExit(0)

if scope == "completion_audit":
    if not completion_writer_path.exists():
        print("launch_writer")
        raise SystemExit(0)
    writer_doc = json.loads(completion_writer_path.read_text())
    if str(writer_doc.get("audited_at") or "") < created:
        print("launch_writer")
        raise SystemExit(0)
    print("processed")
    raise SystemExit(0)

if not decision_path.exists():
    print("launch_writer")
    raise SystemExit(0)
decision_doc = json.loads(decision_path.read_text())
if str(decision_doc.get("scope") or "") != scope:
    print("launch_writer")
    raise SystemExit(0)
if str(decision_doc.get("decided_at") or "") < created:
    print("launch_writer")
    raise SystemExit(0)
print("processed")
PY
}

clear_processed_finder() {
  python - "$repo_root" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
state_dir = repo_root / ".ai" / "dropbox" / "state"
finder_state_path = state_dir / "finder_state.json"
finder_decision_path = state_dir / "finder_decision.json"
completion_writer_path = state_dir / "completion_audit_writer.json"
state = json.loads(finder_state_path.read_text())
pending = state.get("pendingTrigger") or {}
scope = str(pending.get("scope") or "")
trigger_type = str(pending.get("triggerType") or "")

decision_id = ""
if scope == "completion_audit" and completion_writer_path.exists():
    doc = json.loads(completion_writer_path.read_text())
    decision_id = str(doc.get("audit_id") or "")
elif finder_decision_path.exists():
    doc = json.loads(finder_decision_path.read_text())
    decision_id = str(doc.get("decision_id") or "")

state["pendingTrigger"] = None
if trigger_type == "completion_audit":
    state["lastProcessedCompletionScope"] = f"completion_audit::{pending.get('sourceReceiptId') or ''}"
    state["queuedReceiptFollowons"] = []
if decision_id:
    state["lastFinderAuditId"] = decision_id
    state["lastWriterDecisionId"] = decision_id
finder_state_path.write_text(json.dumps(state, indent=2) + "\n")
PY
}

cleanup_terminal_runtime_markers() {
  local lane marker
  for lane in research builder architecture writer-integrator; do
    marker="$(defi_swarm_lane_active_marker_path "$repo_root" "$lane")"
    if [[ -f "$marker" ]]; then
      local pid=""
      pid="$(jq -r '.pid // empty' "$marker" 2>/dev/null || true)"
      if ! defi_swarm_pid_is_running "$pid"; then
        rm -f "$marker"
      fi
    fi
  done
}

write_supervisor_launch

loop=1
while :; do
  write_supervisor_heartbeat "$loop"
  ensure_session
  ensure_active_story
  sync_swarm_state
  "$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --quiet >/dev/null

  queue_receipt_followons
  queue_repeated_failure_trigger
  if ! defi_swarm_has_eligible_stories "$repo_root"; then
    queue_completion_trigger
  fi
  sync_swarm_state
  "$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --quiet >/dev/null

  printf 'persistent-cycle: cycle %s at %s\n' "$loop" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  finder_mode="$(finder_phase)"
  if [[ "$finder_mode" != "none" ]]; then
    printf 'persistent-cycle: finder=%s\n' "$finder_mode"
    case "$finder_mode" in
      launch_architecture)
        "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane architecture --run --prompt-file "$architecture_finder_prompt"
        ;;
      launch_research)
        "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane research --run --prompt-file "$research_finder_prompt"
        ;;
      launch_writer)
        pending_scope="$(jq -r '.pendingTrigger.scope // empty' "$finder_state_json")"
        if [[ "$pending_scope" == "completion_audit" ]]; then
          "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run --prompt-file "$completion_writer_prompt"
        else
          "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run
        fi
        ;;
      processed)
        clear_processed_finder
        sync_swarm_state
        ;;
      malformed)
        printf 'persistent-cycle: finder trigger malformed; waiting for writer cleanup\n'
        ;;
    esac
  elif defi_swarm_has_eligible_stories "$repo_root"; then
    "$script_dir/relaunch_stale_lanes.sh" --repo "$repo_root" --session "$session_name"
  else
    audit_mode="$(completion_audit_mode)"
    printf 'persistent-cycle: completion-audit=%s\n' "$audit_mode"
    case "$audit_mode" in
      launch_architecture)
        "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane architecture --run --prompt-file "$completion_architecture_prompt"
        ;;
      launch_writer)
        "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run --prompt-file "$completion_writer_prompt"
        ;;
      gaps_promoted)
        printf 'persistent-cycle: writer promoted new gap stories; continuing\n'
        ;;
      clean)
        cleanup_terminal_runtime_markers
        sync_swarm_state
        "$script_dir/status_swarm.sh" --repo "$repo_root" --session "$session_name"
        printf 'persistent-cycle: completion audit is clean; stopping\n'
        exit_reason="clean"
        break
        ;;
      waiting_architecture|waiting_writer)
        printf 'persistent-cycle: waiting on completion audit lane output\n'
        ;;
    esac
  fi

  "$script_dir/capture_swarm.sh" --repo "$repo_root" --session "$session_name" >/dev/null
  "$script_dir/status_swarm.sh" --repo "$repo_root" --session "$session_name" >/dev/null

  if [[ "$max_cycles" != "0" && "$loop" -ge "$max_cycles" ]]; then
    exit_reason="bounded_limit"
    break
  fi

  sleep "$interval_seconds"
  loop=$((loop + 1))
done
