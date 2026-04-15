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
      printf 'Usage: status_swarm.sh [--repo PATH] [--session NAME]\n'
      exit 0
      ;;
    *)
      printf 'status_swarm: unknown argument %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"

printf 'active story: %s\n' "$(defi_swarm_active_story "$repo_root")"
defi_swarm_print_lane_map

manifest_file="$HOME/.local/state/ai-frame/tmux-lanes/$session_name/manifest.env"
activity_log="$HOME/.local/state/ai-frame/tmux-lanes/$session_name/lane-activity.log"

printf 'repo: %s\n' "$repo_root"
printf 'session: %s\n' "$session_name"
printf 'manifest: %s\n' "$manifest_file"

if tmux has-session -t "$session_name" >/dev/null 2>&1; then
  printf 'state: running\n'
  tmux list-windows -t "$session_name" -F 'window=#{window_index} name=#{window_name} panes=#{window_panes}'
  while IFS= read -r window_index; do
    tmux list-panes -t "$session_name:$window_index" -F 'pane=#{session_name}:#{window_index}.#{pane_index} active=#{pane_active} title=#{pane_title} path=#{pane_current_path}'
  done < <(tmux list-windows -t "$session_name" -F '#{window_index}')
else
  printf 'state: stopped\n'
fi

printf 'activity_log: %s\n' "$activity_log"
if [[ -f "$manifest_file" ]]; then
  printf '%s\n' 'manifest_values:'
  sed -n '1,40p' "$manifest_file"
fi
if [[ -f "$activity_log" ]]; then
  printf '%s\n' 'recent_activity:'
  tail -n 20 "$activity_log" || true
fi
