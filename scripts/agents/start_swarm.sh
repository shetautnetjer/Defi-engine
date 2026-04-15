#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: start_swarm.sh [--repo PATH] [--session NAME] [--project-id ID] [--launch-all]

Start the Defi-engine four-lane tmux swarm.
EOF
}

repo="${PWD}"
session_name=""
project_id=""
launch_all="false"

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
    --project-id)
      project_id="${2:?--project-id requires a value}"
      shift 2
      ;;
    --launch-all)
      launch_all="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'start_swarm: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
project_id="${project_id:-$(defi_swarm_project_id)}"

defi_swarm_require_repo_files "$repo_root"
defi_swarm_bootstrap_runtime_dirs "$repo_root"

"$(defi_swarm_tmux_root)/tmux_lanes_start.sh" \
  --repo "$repo_root" \
  --lanes 4 \
  --session "$session_name" \
  --project-id "$project_id"

tmux select-pane -t "$session_name:lanes.0" -T "research"
tmux select-pane -t "$session_name:lanes.1" -T "builder"
tmux select-pane -t "$session_name:lanes.2" -T "architecture"
tmux select-pane -t "$session_name:lanes.3" -T "writer-integrator"

printf 'active story: %s\n' "$(defi_swarm_active_story "$repo_root")"
defi_swarm_print_lane_map

if [[ "$launch_all" == "true" ]]; then
  "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane research --run
  "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane builder --run
  "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane architecture --run
  "$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane writer --run
fi

cat <<EOF

Session ready: $session_name
Repo: $repo_root

Common next commands:
  $script_dir/status_swarm.sh --repo $repo_root
  $script_dir/send_swarm.sh --repo $repo_root --lane research --run
  $script_dir/send_swarm.sh --repo $repo_root --lane builder --run
  $script_dir/send_swarm.sh --repo $repo_root --lane architecture --run
  $(defi_swarm_tmux_root)/tmux_lanes_run_ralph.sh --repo $repo_root --lane 4 --tool codex --max-iterations 1
  $script_dir/capture_swarm.sh --repo $repo_root
  $script_dir/stop_swarm.sh --repo $repo_root
EOF
