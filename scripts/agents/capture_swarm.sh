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
      printf 'Usage: capture_swarm.sh [--repo PATH] [--session NAME]\n'
      exit 0
      ;;
    *)
      printf 'capture_swarm: unknown argument %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
capture_dir="$HOME/.local/state/ai-frame/tmux-lanes/$session_name/captures"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
output="$capture_dir/$timestamp.txt"

mkdir -p "$capture_dir"

{
  echo "# defi-engine swarm capture"
  echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "repo: $repo_root"
  echo "session: $session_name"
  echo "lane_selector: all"
  echo
  if tmux has-session -t "$session_name" >/dev/null 2>&1; then
    tmux list-windows -t "$session_name" -F 'window=#{window_index} name=#{window_name} panes=#{window_panes}'
    echo
    while IFS= read -r window_index; do
      while IFS= read -r pane_target; do
        echo "## pane $pane_target"
        tmux capture-pane -p -J -t "$pane_target"
        echo
      done < <(tmux list-panes -t "$session_name:$window_index" -F '#{session_name}:#{window_index}.#{pane_index}')
    done < <(tmux list-windows -t "$session_name" -F '#{window_index}')
  else
    echo "session not running"
  fi
} | tee "$output"

printf 'captured: %s\n' "$output"
