#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: refresh_watch_swarm.sh [--repo PATH] [--session NAME]

Reconfigure the watch window for the Defi-engine swarm so it reflects current
lane health and runtime events.
EOF
}

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
      usage
      exit 0
      ;;
    *)
      printf 'refresh_watch_swarm: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
defi_swarm_bootstrap_runtime_dirs "$repo_root"

if ! tmux has-session -t "$session_name" >/dev/null 2>&1; then
  printf 'refresh_watch_swarm: session %s is not running\n' "$session_name" >&2
  exit 1
fi

activity_log="$HOME/.local/state/ai-frame/tmux-lanes/$session_name/lane-activity.log"
lane_health_md="$(defi_swarm_lane_health_md_path "$repo_root")"
mailbox_path="$(defi_swarm_mailbox_path "$repo_root")"
supervisor_log_path="$(defi_swarm_supervisor_log_path "$repo_root")"

status_loop="while true; do clear; git -C $(printf '%q' "$repo_root") status --short --branch; sleep 2; done"
diff_loop="while true; do clear; git -C $(printf '%q' "$repo_root") diff --stat; sleep 2; done"
health_loop="while true; do clear; $(printf '%q' "$script_dir/health_swarm.sh") --repo $(printf '%q' "$repo_root") --session $(printf '%q' "$session_name") --no-mail --quiet >/dev/null; sed -n '1,160p' $(printf '%q' "$lane_health_md"); sleep 5; done"
events_loop="while true; do clear; printf '%s\n\n' 'mailbox'; tail -n 20 $(printf '%q' "$mailbox_path") 2>/dev/null || true; printf '\n%s\n\n' 'lane activity'; tail -n 20 $(printf '%q' "$activity_log") 2>/dev/null || true; printf '\n%s\n\n' 'supervisor log'; tail -n 20 $(printf '%q' "$supervisor_log_path") 2>/dev/null || true; sleep 5; done"

tmux respawn-pane -k -t "$session_name:watch.0" -c "$repo_root" "bash -lc $(printf '%q' "$status_loop")"
tmux select-pane -t "$session_name:watch.0" -T "git-status"
tmux respawn-pane -k -t "$session_name:watch.1" -c "$repo_root" "bash -lc $(printf '%q' "$diff_loop")"
tmux select-pane -t "$session_name:watch.1" -T "git-diff-stat"
tmux respawn-pane -k -t "$session_name:watch.2" -c "$repo_root" "bash -lc $(printf '%q' "$health_loop")"
tmux select-pane -t "$session_name:watch.2" -T "lane-health"
tmux respawn-pane -k -t "$session_name:watch.3" -c "$repo_root" "bash -lc $(printf '%q' "$events_loop")"
tmux select-pane -t "$session_name:watch.3" -T "swarm-events"
tmux select-layout -t "$session_name:watch" tiled

printf 'watch window refreshed for %s\n' "$session_name"
