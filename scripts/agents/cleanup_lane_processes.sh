#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: cleanup_lane_processes.sh [--repo PATH] [--session NAME] [--lane research|builder|architecture|writer|all]
                               [--story-id ID] [--default-prompt] [--expected-prompt-file FILE]

Interrupt lane pane processes whose active marker contract no longer matches the
expected story or prompt for the current normal story descent.
EOF
}

repo="${PWD}"
session_name=""
lane="all"
story_id=""
default_prompt="false"
expected_prompt_file=""

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
    --lane)
      lane="${2:?--lane requires a value}"
      shift 2
      ;;
    --story-id)
      story_id="${2:?--story-id requires a value}"
      shift 2
      ;;
    --default-prompt)
      default_prompt="true"
      shift
      ;;
    --expected-prompt-file)
      expected_prompt_file="${2:?--expected-prompt-file requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'cleanup_lane_processes: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"

lane_has_codex_process() {
  local lane_name="${1:?lane required}"
  local pane_target pane_pid
  pane_target="$(defi_swarm_lane_tmux_target "$session_name" "$lane_name")"
  if ! pane_pid="$(tmux display-message -p -t "$pane_target" '#{pane_pid}' 2>/dev/null)"; then
    return 1
  fi
  python - "$pane_pid" <<'PY'
from __future__ import annotations

import subprocess
import sys

root_pid = int(sys.argv[1])
raw = subprocess.check_output(["ps", "-eo", "pid=,ppid=,args="], text=True)
children: dict[int, list[tuple[int, str]]] = {}
for line in raw.splitlines():
    line = line.strip()
    if not line:
        continue
    parts = line.split(None, 2)
    if len(parts) < 3:
        continue
    pid, ppid, args = int(parts[0]), int(parts[1]), parts[2]
    children.setdefault(ppid, []).append((pid, args))

stack = [root_pid]
seen: set[int] = set()
while stack:
    current = stack.pop()
    if current in seen:
        continue
    seen.add(current)
    for child_pid, args in children.get(current, []):
        if "codex_run.sh" in args or ".ai/templates/" in args or "codex exec" in args:
            print("yes")
            raise SystemExit(0)
        stack.append(child_pid)

print("no")
PY
}

interrupt_lane() {
  local lane_name="${1:?lane required}"
  local reason="${2:?reason required}"
  local pane_target
  pane_target="$(defi_swarm_lane_tmux_target "$session_name" "$lane_name")"
  tmux respawn-pane -k -t "$pane_target" >/dev/null
  defi_swarm_clear_lane_runtime_markers "$repo_root" "$lane_name"
  defi_swarm_append_mailbox_event "$repo_root" "lane_process_interrupted" "$lane_name" "$story_id" "$session_name" "interrupted" "" "yes" "$reason"
  printf 'cleanup: interrupted %s - %s\n' "$lane_name" "$reason"
}

cleanup_lane() {
  local lane_name="${1:?lane required}"
  local effective_prompt_file="$expected_prompt_file"
  local completion_marker completion_story_id completion_epoch completion_exit_code
  if [[ "$default_prompt" == "true" ]]; then
    effective_prompt_file="$(defi_swarm_prompt_file "$repo_root" "$lane_name")"
  fi

  local active_marker active_story_id active_prompt_file active_pid
  active_marker="$(defi_swarm_lane_active_marker_path "$repo_root" "$lane_name")"
  completion_marker="$(defi_swarm_lane_completion_marker_path "$repo_root" "$lane_name")"
  active_story_id=""
  active_prompt_file=""
  active_pid=""
  completion_story_id=""
  completion_epoch=""
  completion_exit_code=""

  if [[ -f "$active_marker" ]]; then
    active_story_id="$(jq -r '.storyId // ""' "$active_marker" 2>/dev/null || true)"
    active_prompt_file="$(jq -r '.promptFile // ""' "$active_marker" 2>/dev/null || true)"
    active_pid="$(jq -r '.pid // ""' "$active_marker" 2>/dev/null || true)"
    if [[ -n "$active_pid" ]] && ! defi_swarm_pid_is_running "$active_pid"; then
      defi_swarm_clear_lane_runtime_markers "$repo_root" "$lane_name"
      active_story_id=""
      active_prompt_file=""
      active_pid=""
    fi
  fi

  if [[ -n "$active_pid" ]]; then
    if [[ -f "$completion_marker" ]]; then
      completion_story_id="$(jq -r '.storyId // ""' "$completion_marker" 2>/dev/null || true)"
      completion_epoch="$(jq -r '.epoch // ""' "$completion_marker" 2>/dev/null || true)"
      completion_exit_code="$(jq -r '.exitCode // ""' "$completion_marker" 2>/dev/null || true)"
      if [[ "$completion_story_id" == "$active_story_id" && "$completion_exit_code" == "0" && -n "$completion_epoch" ]]; then
        interrupt_lane "$lane_name" "lane completed successfully but its pane process is still alive"
        return 0
      fi
    fi
    if [[ -n "$story_id" && "$active_story_id" != "$story_id" ]]; then
      interrupt_lane "$lane_name" "marker storyId '$active_story_id' does not match expected story '$story_id'"
      return 0
    fi
    if [[ -n "$effective_prompt_file" && "$active_prompt_file" != "$effective_prompt_file" ]]; then
      interrupt_lane "$lane_name" "marker promptFile '$active_prompt_file' does not match expected prompt '$effective_prompt_file'"
      return 0
    fi
    return 0
  fi

  if [[ "$(lane_has_codex_process "$lane_name")" == "yes" ]]; then
    interrupt_lane "$lane_name" "pane has a codex worker but no live matching lane marker"
  fi
}

if [[ "$lane" == "all" ]]; then
  for lane_name in research builder architecture writer-integrator; do
    cleanup_lane "$lane_name"
  done
else
  cleanup_lane "$lane"
fi
