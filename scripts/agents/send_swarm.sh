#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: send_swarm.sh [--repo PATH] [--session NAME] --lane research|builder|architecture|writer|all [--run]
                     [--prompt TEXT | --prompt-file FILE] [--model MODEL]
                     [--story-id ID] [--scope SCOPE] [--mode story|finder|completion_audit]

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
explicit_story_id=""
scope=""
mode=""

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
    --story-id)
      explicit_story_id="${2:?--story-id requires a value}"
      shift 2
      ;;
    --scope)
      scope="${2:?--scope requires a value}"
      shift 2
      ;;
    --mode)
      mode="${2:?--mode requires a value}"
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
story_id="${explicit_story_id:-$(defi_swarm_active_story "$repo_root")}"

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
  prompt_type="$(defi_swarm_prompt_type_from_file "$prompt_file")"
  finder_state_path="$(defi_swarm_finder_state_path "$repo_root")"
  pending_scope=""
  pending_story_id=""
  if [[ -f "$finder_state_path" ]]; then
    pending_scope="$(jq -r '.pendingTrigger.scope // empty' "$finder_state_path" 2>/dev/null || true)"
    pending_story_id="$(jq -r '.pendingTrigger.storyId // empty' "$finder_state_path" 2>/dev/null || true)"
  fi
  if [[ -z "$mode" ]]; then
    case "$prompt_type" in
      architecture_finder|research_finder) mode="finder" ;;
      architecture_completion_audit|writer_completion_audit) mode="completion_audit" ;;
      *) mode="story" ;;
    esac
  fi
  if [[ -z "$scope" ]]; then
    case "$mode" in
      finder) scope="$pending_scope" ;;
      completion_audit) scope="completion_audit" ;;
      *) scope="$story_id" ;;
    esac
  fi
  if [[ "$mode" != "story" && -z "$story_id" ]]; then
    story_id="$pending_story_id"
  fi
  if [[ "$mode" != "story" && -z "$scope" ]]; then
    printf 'send_swarm: scope is required for %s runs\n' "$mode" >&2
    exit 2
  fi
  launch_marker="$(defi_swarm_lane_launch_marker_path "$repo_root" "$lane")"
  completion_marker="$(defi_swarm_lane_completion_marker_path "$repo_root" "$lane")"
  active_marker="$(defi_swarm_lane_active_marker_path "$repo_root" "$lane")"
  heartbeat_marker="$(defi_swarm_lane_heartbeat_path "$repo_root" "$lane")"
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  started_epoch="$(date -u +%s)"
  jq -nc \
    --arg ts "$started_at" \
    --arg startedAt "$started_at" \
    --arg lane "$lane" \
    --arg storyId "$story_id" \
    --arg scope "$scope" \
    --arg mode "$mode" \
    --arg promptFile "$prompt_file" \
    --arg promptType "$prompt_type" \
    --arg session "$session_name" \
    --argjson epoch "$started_epoch" \
    '{ts:$ts, startedAt:$startedAt, epoch:$epoch, lane:$lane, storyId:$storyId, scope:$scope, mode:$mode, promptFile:$promptFile, promptType:$promptType, session:$session}' > "$launch_marker"
  payload="cd $(printf '%q' "$repo_root") && _defi_started_at=\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"; _defi_started_epoch=\"\$(date -u +%s)\"; jq -nc --arg ts \"\$_defi_started_at\" --arg startedAt \"\$_defi_started_at\" --arg lane $(printf '%q' "$lane") --arg storyId $(printf '%q' "$story_id") --arg scope $(printf '%q' "$scope") --arg mode $(printf '%q' "$mode") --arg promptFile $(printf '%q' "$prompt_file") --arg promptType $(printf '%q' "$prompt_type") --arg session $(printf '%q' "$session_name") --argjson epoch \"\$_defi_started_epoch\" --argjson pid \"\$\$\" '{ts:\$ts, startedAt:\$startedAt, epoch:\$epoch, lane:\$lane, storyId:\$storyId, scope:\$scope, mode:\$mode, promptFile:\$promptFile, promptType:\$promptType, session:\$session, pid:\$pid}' > $(printf '%q' "$active_marker"); (while kill -0 \"\$\$\" 2>/dev/null; do jq -nc --arg ts \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\" --arg startedAt \"\$_defi_started_at\" --arg lane $(printf '%q' "$lane") --arg storyId $(printf '%q' "$story_id") --arg scope $(printf '%q' "$scope") --arg mode $(printf '%q' "$mode") --arg promptFile $(printf '%q' "$prompt_file") --arg promptType $(printf '%q' "$prompt_type") --arg session $(printf '%q' "$session_name") --argjson epoch \"\$(date -u +%s)\" --argjson pid \"\$\$\" '{ts:\$ts, startedAt:\$startedAt, epoch:\$epoch, lane:\$lane, storyId:\$storyId, scope:\$scope, mode:\$mode, promptFile:\$promptFile, promptType:\$promptType, session:\$session, pid:\$pid}' > $(printf '%q' "$heartbeat_marker"); sleep 30; done) & _defi_heartbeat_pid=\$!; trap 'kill \"\$_defi_heartbeat_pid\" 2>/dev/null || true; rm -f $(printf '%q' "$active_marker") $(printf '%q' "$heartbeat_marker")' EXIT; $runner_args; _defi_status=\$?; jq -nc --arg ts \"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\" --arg startedAt \"\$_defi_started_at\" --arg lane $(printf '%q' "$lane") --arg storyId $(printf '%q' "$story_id") --arg scope $(printf '%q' "$scope") --arg mode $(printf '%q' "$mode") --arg promptFile $(printf '%q' "$prompt_file") --arg promptType $(printf '%q' "$prompt_type") --arg session $(printf '%q' "$session_name") --argjson epoch \"\$(date -u +%s)\" --argjson exitCode \"\$_defi_status\" '{ts:\$ts, startedAt:\$startedAt, epoch:\$epoch, lane:\$lane, storyId:\$storyId, scope:\$scope, mode:\$mode, promptFile:\$promptFile, promptType:\$promptType, session:\$session, exitCode:\$exitCode}' > $(printf '%q' "$completion_marker"); exit \$_defi_status"
  command_text="$(printf 'bash -lc %q' "$payload")"
  defi_swarm_append_mailbox_event "$repo_root" "lane_launch" "$lane" "$story_id" "$session_name" "" "" "" "lane run requested" "$scope" "$mode"
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
