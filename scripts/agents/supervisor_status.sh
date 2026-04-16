#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: supervisor_status.sh [--repo PATH] [--json]

Show detached supervisor state for the Defi-engine swarm.
EOF
}

repo="${PWD}"
json_mode="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    --json)
      json_mode="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'supervisor_status: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
pid_path="$(defi_swarm_supervisor_pid_path "$repo_root")"
log_path="$(defi_swarm_supervisor_log_path "$repo_root")"
launch_path="$(defi_swarm_supervisor_launch_path "$repo_root")"
heartbeat_path="$(defi_swarm_supervisor_heartbeat_path "$repo_root")"
last_exit_path="$(defi_swarm_supervisor_last_exit_path "$repo_root")"

pid=""
if [[ -f "$pid_path" ]]; then
  pid="$(tr -d '[:space:]' < "$pid_path")"
fi

status="stopped"
if [[ -n "$pid" ]]; then
  if defi_swarm_pid_is_running "$pid"; then
    status="running"
  else
    status="stale_pid"
  fi
elif [[ -f "$last_exit_path" ]] && jq -e '(.exitCode // 0) != 0' "$last_exit_path" >/dev/null 2>&1; then
  status="failed_recently"
fi

launch_ts=""
interval_seconds=""
if [[ -f "$launch_path" ]]; then
  launch_ts="$(jq -r '.ts // ""' "$launch_path")"
  interval_seconds="$(jq -r '(.intervalSeconds // "") | tostring' "$launch_path")"
fi

heartbeat_ts=""
heartbeat_cycle=""
heartbeat_story=""
if [[ -f "$heartbeat_path" ]]; then
  heartbeat_ts="$(jq -r '.ts // ""' "$heartbeat_path")"
  heartbeat_cycle="$(jq -r '(.cycle // "") | tostring' "$heartbeat_path")"
  heartbeat_story="$(jq -r '.activeStoryId // ""' "$heartbeat_path")"
fi

last_exit_ts=""
last_exit_code=""
last_exit_reason=""
last_exit_signal=""
if [[ -f "$last_exit_path" ]]; then
  last_exit_ts="$(jq -r '.ts // ""' "$last_exit_path")"
  last_exit_code="$(jq -r '(.exitCode // "") | tostring' "$last_exit_path")"
  last_exit_reason="$(jq -r '.reason // ""' "$last_exit_path")"
  last_exit_signal="$(jq -r '.signal // ""' "$last_exit_path")"
fi

if [[ "$json_mode" == "true" ]]; then
  jq -nc \
    --arg status "$status" \
    --arg pid "$pid" \
    --arg logPath "$log_path" \
    --arg launchPath "$launch_path" \
    --arg heartbeatPath "$heartbeat_path" \
    --arg lastExitPath "$last_exit_path" \
    --arg launchTs "$launch_ts" \
    --arg intervalSeconds "$interval_seconds" \
    --arg heartbeatTs "$heartbeat_ts" \
    --arg heartbeatCycle "$heartbeat_cycle" \
    --arg heartbeatStory "$heartbeat_story" \
    --arg lastExitTs "$last_exit_ts" \
    --arg lastExitCode "$last_exit_code" \
    --arg lastExitReason "$last_exit_reason" \
    --arg lastExitSignal "$last_exit_signal" \
    '{
      status: $status,
      pid: ($pid | select(length > 0)),
      logPath: $logPath,
      launchPath: $launchPath,
      heartbeatPath: $heartbeatPath,
      lastExitPath: $lastExitPath,
      launchTs: ($launchTs | select(length > 0)),
      intervalSeconds: ($intervalSeconds | select(length > 0)),
      heartbeatTs: ($heartbeatTs | select(length > 0)),
      heartbeatCycle: ($heartbeatCycle | select(length > 0)),
      activeStoryId: ($heartbeatStory | select(length > 0)),
      lastExitTs: ($lastExitTs | select(length > 0)),
      lastExitCode: ($lastExitCode | select(length > 0)),
      lastExitReason: ($lastExitReason | select(length > 0)),
      lastExitSignal: ($lastExitSignal | select(length > 0))
    }'
  exit 0
fi

printf 'status=%s\n' "$status"
printf 'pid=%s\n' "${pid:-none}"
printf 'interval_seconds=%s\n' "${interval_seconds:-unknown}"
printf 'launch_time=%s\n' "${launch_ts:-none}"
printf 'last_heartbeat=%s\n' "${heartbeat_ts:-none}"
printf 'heartbeat_cycle=%s\n' "${heartbeat_cycle:-none}"
printf 'active_story=%s\n' "${heartbeat_story:-none}"
printf 'last_exit_time=%s\n' "${last_exit_ts:-none}"
printf 'last_exit_code=%s\n' "${last_exit_code:-none}"
printf 'last_exit_reason=%s\n' "${last_exit_reason:-none}"
printf 'last_exit_signal=%s\n' "${last_exit_signal:-none}"
printf 'log_path=%s\n' "$log_path"
