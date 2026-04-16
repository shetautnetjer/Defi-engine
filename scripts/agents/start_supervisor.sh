#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: start_supervisor.sh [--repo PATH] [--session NAME] [--interval SECONDS]

Start the detached continuous supervisor for the Defi-engine swarm.
EOF
}

repo="${PWD}"
session_name=""
interval_seconds="30"

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
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'start_supervisor: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
defi_swarm_bootstrap_runtime_dirs "$repo_root"

pid_path="$(defi_swarm_supervisor_pid_path "$repo_root")"
log_path="$(defi_swarm_supervisor_log_path "$repo_root")"

existing_pid=""
if [[ -f "$pid_path" ]]; then
  existing_pid="$(tr -d '[:space:]' < "$pid_path")"
fi

if [[ -n "$existing_pid" ]] && defi_swarm_pid_is_running "$existing_pid"; then
  printf 'supervisor already running\n'
  "$script_dir/supervisor_status.sh" --repo "$repo_root"
  exit 0
fi

if [[ -n "$existing_pid" ]]; then
  rm -f "$pid_path"
fi

mkdir -p "$(dirname "$log_path")"
printf '\n[%s] start_supervisor interval=%s session=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$interval_seconds" "$session_name" >> "$log_path"

setsid "$script_dir/run_persistent_cycle.sh" \
  --repo "$repo_root" \
  --session "$session_name" \
  --interval "$interval_seconds" \
  --start-if-missing >> "$log_path" 2>&1 < /dev/null &
supervisor_pid=$!
printf '%s\n' "$supervisor_pid" > "$pid_path"

sleep 1
if ! defi_swarm_pid_is_running "$supervisor_pid"; then
  printf 'start_supervisor: process exited before becoming healthy\n' >&2
  "$script_dir/supervisor_status.sh" --repo "$repo_root" || true
  tail -n 40 "$log_path" >&2 || true
  exit 1
fi

printf 'started detached supervisor pid=%s\n' "$supervisor_pid"
"$script_dir/supervisor_status.sh" --repo "$repo_root"
