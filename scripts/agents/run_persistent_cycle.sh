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
swarm_state_helper="$script_dir/swarm_state.py"
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
performance_receipts_dir="$(defi_swarm_performance_receipts_dir "$repo_root")"
supervisor_launch_json="$(defi_swarm_supervisor_launch_path "$repo_root")"
supervisor_heartbeat_json="$(defi_swarm_supervisor_heartbeat_path "$repo_root")"
supervisor_last_exit_json="$(defi_swarm_supervisor_last_exit_path "$repo_root")"
run_mode="continuous"
if [[ "$max_cycles" != "0" ]]; then
  run_mode="bounded"
fi
exit_reason="running"
exit_signal=""
supervisor_mode="execution"

write_supervisor_launch() {
  jq -nc \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg repo "$repo_root" \
    --arg session "$session_name" \
    --argjson pid "$$" \
    --argjson interval "$interval_seconds" \
    --arg supervisorMode "$supervisor_mode" \
    --arg mode "$run_mode" \
    --argjson maxCycles "$max_cycles" \
    '{ts:$ts, repo:$repo, session:$session, pid:$pid, intervalSeconds:$interval, mode:$mode, supervisorMode:$supervisorMode, maxCycles:$maxCycles}' > "$supervisor_launch_json"
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
    --arg supervisorMode "$supervisor_mode" \
    --argjson pid "$$" \
    --argjson cycle "$cycle" \
    --argjson interval "$interval_seconds" \
    '{ts:$ts, repo:$repo, session:$session, pid:$pid, cycle:$cycle, intervalSeconds:$interval, mode:$mode, supervisorMode:$supervisorMode, activeStoryId:$storyId}' > "$supervisor_heartbeat_json"
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
    --arg supervisorMode "$supervisor_mode" \
    --argjson pid "$$" \
    --argjson exitCode "$exit_code" \
    '{ts:$ts, repo:$repo, session:$session, pid:$pid, mode:$mode, supervisorMode:$supervisorMode, exitCode:$exitCode, reason:$reason, signal:($signal | select(length > 0))}' > "$supervisor_last_exit_json"
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

lane_has_active_scope_mode() {
  local lane_name="${1:?lane required}"
  local scope="${2:?scope required}"
  local mode="${3:?mode required}"
  jq -e \
    --arg lane "$lane_name" \
    --arg scope "$scope" \
    --arg mode "$mode" \
    '
    .lanes[]
    | select(.name == $lane)
    | (.activePid != null)
      and ((.activeScope // "") == $scope)
      and ((.activeMode // "") == $mode)
    ' "$lane_health_json" >/dev/null
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

  if lane_has_active_scope_mode architecture completion_audit completion_audit || [[ "$(lane_status architecture)" == "running" ]]; then
    printf 'waiting_architecture\n'
    return 0
  fi
  if lane_has_active_scope_mode writer-integrator completion_audit completion_audit || [[ "$(lane_status writer-integrator)" == "running" ]]; then
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
  python "$swarm_state_helper" --repo "$repo_root" queue-receipt-followons
}

queue_performance_trigger() {
  python "$swarm_state_helper" --repo "$repo_root" queue-performance-trigger
}

queue_repeated_failure_trigger() {
  python "$swarm_state_helper" --repo "$repo_root" queue-repeated-failure-trigger
}

queue_completion_trigger() {
  python "$swarm_state_helper" --repo "$repo_root" queue-completion-trigger
}

queue_periodic_terminal_audit() {
  # Queue the periodic_completion_audit finder trigger once terminal monitoring ages out.
  python "$swarm_state_helper" --repo "$repo_root" queue-periodic-terminal-audit
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

clear_stale_completion_trigger() {
  python "$swarm_state_helper" --repo "$repo_root" clear-stale-completion-trigger
}

clear_processed_finder() {
  python "$swarm_state_helper" --repo "$repo_root" clear-processed-finder
}

cleanup_terminal_runtime_markers() {
  local lane marker
  for lane in research builder architecture writer-integrator; do
    marker="$(defi_swarm_lane_active_marker_path "$repo_root" "$lane")"
    if [[ -f "$marker" ]]; then
      local pid=""
      pid="$(jq -r '.pid // empty' "$marker" 2>/dev/null || true)"
      if ! defi_swarm_pid_is_running "$pid"; then
        defi_swarm_clear_lane_runtime_markers "$repo_root" "$lane"
      fi
    fi
  done
}

auto_commit_latest_receipt() {
  "$script_dir/commit_accepted_story.sh" --repo "$repo_root" >/dev/null || true
}

write_supervisor_launch

loop=1
while :; do
  write_supervisor_heartbeat "$loop"
  ensure_session
  ensure_active_story
  sync_swarm_state
  "$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --quiet >/dev/null

  "$script_dir/sync_performance_receipts.sh" --repo "$repo_root" >/dev/null || true
  queue_receipt_followons
  queue_performance_trigger
  if defi_swarm_has_eligible_stories "$repo_root"; then
    queue_repeated_failure_trigger
  fi
  if ! defi_swarm_has_eligible_stories "$repo_root"; then
    queue_completion_trigger
    queue_periodic_terminal_audit
  fi
  sync_swarm_state
  clear_stale_completion_trigger
  "$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --quiet >/dev/null

  printf 'persistent-cycle: cycle %s at %s\n' "$loop" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  finder_mode="$(finder_phase)"
  if [[ "$finder_mode" != "none" ]]; then
    supervisor_mode="execution"
    printf 'persistent-cycle: finder=%s\n' "$finder_mode"
    case "$finder_mode" in
      launch_architecture)
        if [[ "$(lane_status architecture)" == "running" ]]; then
          printf 'persistent-cycle: waiting on architecture finder output\n'
        else
          pending_scope="$(jq -r '.pendingTrigger.scope // empty' "$finder_state_json")"
          pending_story_id="$(jq -r '.pendingTrigger.storyId // empty' "$finder_state_json")"
          "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane architecture --run --prompt-file "$architecture_finder_prompt" --scope "$pending_scope" --mode finder --story-id "$pending_story_id"
        fi
        ;;
      launch_research)
        if [[ "$(lane_status research)" == "running" ]]; then
          printf 'persistent-cycle: waiting on research finder output\n'
        else
          pending_scope="$(jq -r '.pendingTrigger.scope // empty' "$finder_state_json")"
          pending_story_id="$(jq -r '.pendingTrigger.storyId // empty' "$finder_state_json")"
          "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane research --run --prompt-file "$research_finder_prompt" --scope "$pending_scope" --mode finder --story-id "$pending_story_id"
        fi
        ;;
      launch_writer)
        if [[ "$(lane_status writer-integrator)" == "running" ]]; then
          printf 'persistent-cycle: waiting on writer finder output\n'
        else
          pending_scope="$(jq -r '.pendingTrigger.scope // empty' "$finder_state_json")"
          pending_story_id="$(jq -r '.pendingTrigger.storyId // empty' "$finder_state_json")"
          if [[ "$pending_scope" == "completion_audit" ]]; then
            "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run --prompt-file "$completion_writer_prompt" --scope "$pending_scope" --mode completion_audit --story-id "$pending_story_id"
          else
            "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run --scope "$pending_scope" --mode finder --story-id "$pending_story_id"
          fi
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
    supervisor_mode="execution"
    "$script_dir/relaunch_stale_lanes.sh" --repo "$repo_root" --session "$session_name"
  else
    audit_mode="$(completion_audit_mode)"
    printf 'persistent-cycle: completion-audit=%s\n' "$audit_mode"
    case "$audit_mode" in
      launch_architecture)
        "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane architecture --run --prompt-file "$completion_architecture_prompt" --scope completion_audit --mode completion_audit --story-id ""
        ;;
      launch_writer)
        "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run --prompt-file "$completion_writer_prompt" --scope completion_audit --mode completion_audit --story-id ""
        ;;
      gaps_promoted)
        supervisor_mode="execution"
        printf 'persistent-cycle: writer promoted new gap stories; continuing\n'
        ;;
      clean)
        supervisor_mode="terminal_monitoring"
        cleanup_terminal_runtime_markers
        sync_swarm_state
        "$script_dir/status_swarm.sh" --repo "$repo_root" --session "$session_name" >/dev/null
        printf 'persistent-cycle: completion audit is clean; entering terminal monitoring\n'
        ;;
      waiting_architecture|waiting_writer)
        supervisor_mode="execution"
        printf 'persistent-cycle: waiting on completion audit lane output\n'
        ;;
    esac
  fi

  "$script_dir/capture_swarm.sh" --repo "$repo_root" --session "$session_name" >/dev/null
  "$script_dir/status_swarm.sh" --repo "$repo_root" --session "$session_name" >/dev/null
  auto_commit_latest_receipt

  if [[ "$max_cycles" != "0" && "$loop" -ge "$max_cycles" ]]; then
    exit_reason="bounded_limit"
    break
  fi

  sleep "$interval_seconds"
  loop=$((loop + 1))
done
