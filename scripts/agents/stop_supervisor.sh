#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: stop_supervisor.sh [--repo PATH]

Stop the detached continuous supervisor for the Defi-engine swarm.
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
      printf 'stop_supervisor: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
pid_path="$(defi_swarm_supervisor_pid_path "$repo_root")"

if [[ ! -f "$pid_path" ]]; then
  printf 'supervisor not running\n'
  exit 0
fi

pid="$(tr -d '[:space:]' < "$pid_path")"
if [[ -z "$pid" ]]; then
  rm -f "$pid_path"
  printf 'supervisor not running\n'
  exit 0
fi

if ! defi_swarm_pid_is_running "$pid"; then
  rm -f "$pid_path"
  printf 'removed stale supervisor pid %s\n' "$pid"
  exit 0
fi

kill "$pid" 2>/dev/null || true
for _ in $(seq 1 40); do
  if ! defi_swarm_pid_is_running "$pid"; then
    break
  fi
  sleep 0.25
done

if defi_swarm_pid_is_running "$pid"; then
  kill -KILL "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    if ! defi_swarm_pid_is_running "$pid"; then
      break
    fi
    sleep 0.25
  done
fi

if defi_swarm_pid_is_running "$pid"; then
  printf 'stop_supervisor: pid %s did not exit after TERM or KILL\n' "$pid" >&2
  exit 1
fi

rm -f "$pid_path"
printf 'stopped supervisor pid=%s\n' "$pid"
