#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: send_swarm.sh [--repo PATH] [--session NAME] --lane research|builder|architecture|writer|all [--run] [--prompt TEXT | --prompt-file FILE] [--model MODEL]

Send a prompt to a lane or launch a lane-local codex exec run.
EOF
}

repo="${PWD}"
session_name=""
lane=""
run_mode="false"
prompt_text=""
prompt_file=""
model=""

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
    --run)
      run_mode="true"
      shift
      ;;
    --prompt)
      prompt_text="${2:?--prompt requires a value}"
      shift 2
      ;;
    --prompt-file)
      prompt_file="${2:?--prompt-file requires a value}"
      shift 2
      ;;
    --model)
      model="${2:?--model requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'send_swarm: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$lane" ]]; then
  printf 'send_swarm: --lane is required\n' >&2
  usage >&2
  exit 2
fi

if [[ "$run_mode" == "true" && "$lane" == "all" ]]; then
  printf 'send_swarm: --run requires a single lane, not all\n' >&2
  exit 2
fi

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
lane_target="$(defi_swarm_lane_number "$lane")"
story_id="$(defi_swarm_active_story "$repo_root")"

if [[ "$run_mode" == "true" ]]; then
  if [[ -z "$prompt_file" ]]; then
    prompt_file="$(defi_swarm_prompt_file "$repo_root" "$lane")"
  fi
  if [[ ! -f "$prompt_file" ]]; then
    printf 'send_swarm: prompt file not found: %s\n' "$prompt_file" >&2
    exit 1
  fi

  runner_args="$(printf '%q --repo %q --run-name %q' \
    "$(defi_swarm_codex_runner)" \
    "$repo_root" \
    "swarm-$lane")"

  default_model="$(defi_swarm_default_model_for_lane "$lane")"
  effective_model="${model:-$default_model}"
  if [[ -n "$effective_model" ]]; then
    runner_args+=" --extra-arg -m --extra-arg $(printf '%q' "$effective_model")"
  elif [[ -n "$model" ]]; then
    runner_args+=" --extra-arg -m --extra-arg $(printf '%q' "$model")"
  fi

  runner_args+=" --prompt-file $(printf '%q' "$prompt_file")"
  launch_marker="$(defi_swarm_lane_launch_marker_path "$repo_root" "$lane")"
  completion_marker="$(defi_swarm_lane_completion_marker_path "$repo_root" "$lane")"
  active_marker="$(defi_swarm_lane_active_marker_path "$repo_root" "$lane")"
  jq -nc \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg lane "$lane" \
    --arg storyId "$story_id" \
    --arg promptFile "$prompt_file" \
    --arg session "$session_name" \
    --argjson epoch "$(date -u +%s)" \
    '{ts:$ts, epoch:$epoch, lane:$lane, storyId:$storyId, promptFile:$promptFile, session:$session}' > "$launch_marker"
  payload="cd $(printf '%q' "$repo_root") && jq -nc --arg ts \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\" --arg lane $(printf '%q' "$lane") --arg storyId $(printf '%q' "$story_id") --arg promptFile $(printf '%q' "$prompt_file") --arg session $(printf '%q' "$session_name") --argjson epoch \"\$(date -u +%s)\" --argjson pid \"\$\$\" '{ts:\$ts, epoch:\$epoch, lane:\$lane, storyId:\$storyId, promptFile:\$promptFile, session:\$session, pid:\$pid}' > $(printf '%q' "$active_marker"); trap 'rm -f $(printf '%q' "$active_marker")' EXIT; $runner_args; _defi_status=\$?; jq -nc --arg ts \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\" --arg lane $(printf '%q' "$lane") --arg storyId $(printf '%q' "$story_id") --arg promptFile $(printf '%q' "$prompt_file") --arg session $(printf '%q' "$session_name") --argjson epoch \"\$(date -u +%s)\" --argjson exitCode \"\$_defi_status\" '{ts:\$ts, epoch:\$epoch, lane:\$lane, storyId:\$storyId, promptFile:\$promptFile, session:\$session, exitCode:\$exitCode}' > $(printf '%q' "$completion_marker"); exit \$_defi_status"
  command_text="$(printf 'bash -lc %q' "$payload")"
  defi_swarm_append_mailbox_event "$repo_root" "lane_launch" "$lane" "$story_id" "$session_name" "" "" "" "lane run requested"
  "$(defi_swarm_tmux_root)/tmux_lanes_send.sh" --repo "$repo_root" --session "$session_name" --lane "$lane_target" --prompt "$command_text"
  exit 0
fi

if [[ -n "$prompt_text" && -n "$prompt_file" ]]; then
  printf 'send_swarm: choose --prompt or --prompt-file, not both\n' >&2
  exit 2
fi
if [[ -z "$prompt_text" && -z "$prompt_file" ]]; then
  printf 'send_swarm: one of --prompt or --prompt-file is required when --run is not used\n' >&2
  exit 2
fi

if [[ -n "$prompt_file" ]]; then
  "$(defi_swarm_tmux_root)/tmux_lanes_send.sh" --repo "$repo_root" --session "$session_name" --lane "$lane_target" --prompt-file "$prompt_file"
else
  "$(defi_swarm_tmux_root)/tmux_lanes_send.sh" --repo "$repo_root" --session "$session_name" --lane "$lane_target" --prompt "$prompt_text"
fi
