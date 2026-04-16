#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

repo="${PWD}"
session_name=""

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
    -h|--help)
      printf 'Usage: stop_swarm.sh [--repo PATH] [--session NAME]\n'
      exit 0
      ;;
    *)
      printf 'stop_swarm: unknown argument %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
"$script_dir/stop_supervisor.sh" --repo "$repo_root" >/dev/null || true
"$(defi_swarm_tmux_root)/tmux_lanes_stop.sh" --repo "$repo_root" --session "$session_name" --kill
