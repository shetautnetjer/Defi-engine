#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: relaunch_stale_lanes.sh [--repo PATH] [--session NAME] [--dry-run]

Refresh lane health and relaunch only the highest-priority stale or failed lane
that is safe to restart.
EOF
}

repo="${PWD}"
session_name=""
dry_run="false"

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
    --dry-run)
      dry_run="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'relaunch_stale_lanes: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
"$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --quiet

active_story="$(defi_swarm_active_story "$repo_root")"
if [[ -n "$active_story" && "$active_story" != "null" ]]; then
  "$script_dir/cleanup_lane_processes.sh" \
    --repo "$repo_root" \
    --session "$session_name" \
    --lane all \
    --story-id "$active_story" \
    --default-prompt >/dev/null || true
  "$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --quiet
fi

lane_health_json="$(defi_swarm_lane_health_json_path "$repo_root")"
story_state="$(jq -r '.story.state // "missing"' "$lane_health_json")"
story_eligible="$(jq -r '.story.eligible // false' "$lane_health_json")"
next_eligible_story="$(jq -r '.story.nextEligibleStoryId // empty' "$lane_health_json")"
accepted_state="$(jq -r '.story.acceptedState // "none"' "$lane_health_json")"
path_exhausted="$(jq -r '.story.pathExhausted // false' "$lane_health_json")"

lane_status() {
  local lane_name="${1:?lane required}"
  jq -r --arg lane "$lane_name" '.lanes[] | select(.name == $lane) | .status' "$lane_health_json"
}

lane_should_restart() {
  local lane_name="${1:?lane required}"
  jq -r --arg lane "$lane_name" '.lanes[] | select(.name == $lane and .restartRecommendation == "yes") | .status' "$lane_health_json"
}

restart_lane=""
restart_status=""
research_status="$(lane_status research)"
architecture_status="$(lane_status architecture)"
builder_status="$(lane_status builder)"
writer_status="$(lane_status writer-integrator)"

if [[ "$accepted_state" == "complete" ]]; then
  printf 'story %s is already accepted and promoted; no relaunch needed\n' "$active_story"
  exit 0
fi

if [[ "$story_eligible" != "true" ]]; then
  if [[ -n "$next_eligible_story" && "$next_eligible_story" != "$active_story" ]]; then
    restart_lane="writer-integrator"
    restart_status="stale"
  else
    printf 'no eligible stories available for relaunch (story state: %s)\n' "$story_state"
    exit 0
  fi
elif [[ "$path_exhausted" == "true" ]]; then
  status="$(lane_should_restart writer-integrator)"
  if [[ -n "$status" ]]; then
    restart_lane="writer-integrator"
    restart_status="$status"
  else
    printf 'architecture marked the path exhausted; waiting on writer-integrator\n'
    exit 0
  fi
else
  if [[ "$builder_status" == "completed" ]]; then
    status="$(lane_should_restart writer-integrator)"
    if [[ -n "$status" ]]; then
      restart_lane="writer-integrator"
      restart_status="$status"
    elif [[ "$writer_status" != "running" ]]; then
      restart_lane="writer-integrator"
      restart_status="${writer_status:-stale}"
    fi
  fi
  if [[ -z "$restart_lane" ]]; then
    status="$(lane_should_restart research)"
    if [[ -n "$status" ]]; then
      restart_lane="research"
      restart_status="$status"
    elif [[ "$research_status" != "running" ]]; then
      status="$(lane_should_restart architecture)"
      if [[ -n "$status" ]]; then
        restart_lane="architecture"
        restart_status="$status"
      elif [[ "$architecture_status" != "running" ]]; then
        status="$(lane_should_restart builder)"
        if [[ -n "$status" ]]; then
          restart_lane="builder"
          restart_status="$status"
        elif [[ "$builder_status" != "running" ]]; then
          status="$(lane_should_restart writer-integrator)"
          if [[ -n "$status" ]]; then
            restart_lane="writer-integrator"
            restart_status="$status"
          fi
        fi
      fi
    fi
  fi
fi

if [[ -z "$restart_lane" ]]; then
  printf 'no stale lanes to relaunch\n'
  exit 0
fi

reason="$(jq -r --arg lane "$restart_lane" '.lanes[] | select(.name == $lane) | .reason' "$lane_health_json")"
printf 'candidate: %s (%s) - %s\n' "$restart_lane" "$restart_status" "$reason"

if [[ "$dry_run" == "true" ]]; then
  exit 0
fi

defi_swarm_append_mailbox_event "$repo_root" "lane_relaunch_requested" "$restart_lane" "$active_story" "$session_name" "$restart_status" "" "yes" "$reason"
"$script_dir/send_swarm.sh" --repo "$repo_root" --session "$session_name" --lane "$restart_lane" --run
