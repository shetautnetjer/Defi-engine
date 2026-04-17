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
defi_swarm_bootstrap_runtime_dirs "$repo_root"
"$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --no-mail --quiet >/dev/null

printf 'active story: %s\n' "$(defi_swarm_active_story "$repo_root")"
defi_swarm_print_lane_map

manifest_file="$HOME/.local/state/ai-frame/tmux-lanes/$session_name/manifest.env"
activity_log="$HOME/.local/state/ai-frame/tmux-lanes/$session_name/lane-activity.log"
lane_health_md="$(defi_swarm_lane_health_md_path "$repo_root")"
lane_health_json="$(defi_swarm_lane_health_json_path "$repo_root")"
mailbox_path="$(defi_swarm_mailbox_path "$repo_root")"
mailbox_current_path="$(defi_swarm_mailbox_current_path "$repo_root")"
finder_state_path="$(defi_swarm_finder_state_path "$repo_root")"
performance_receipts_dir="$(defi_swarm_performance_receipts_dir "$repo_root")"

printf 'repo: %s\n' "$repo_root"
printf 'session: %s\n' "$session_name"
printf 'manifest: %s\n' "$manifest_file"
printf 'lane_health: %s\n' "$lane_health_md"
printf 'mailbox: %s\n' "$mailbox_path"
printf 'mailbox_current: %s\n' "$mailbox_current_path"
printf '%s\n' 'supervisor_summary:'
"$script_dir/supervisor_status.sh" --repo "$repo_root" | sed 's/^/  /'
if [[ -f "$finder_state_path" ]]; then
  printf '%s\n' 'governance_summary:'
  jq -r '
    [
      "pending_trigger_type=" + (.pendingTrigger.triggerType // "none"),
      "pending_trigger_scope=" + (.pendingTrigger.scope // "none"),
      "last_processed_performance_receipt=" + (.lastProcessedPerformanceReceiptId // "none"),
      "last_terminal_audit=" + (.lastTerminalAuditAt // "none")
    ] | .[]' "$finder_state_path" | sed 's/^/  /'
fi
if compgen -G "$performance_receipts_dir/*.json" > /dev/null; then
  printf '%s\n' 'latest_performance_receipt:'
  latest_performance_receipt="$(ls -1 "$performance_receipts_dir"/*.json | sort | tail -n 1)"
  jq -r '
    [
      "receipt_id=" + (.receipt_id // "none"),
      "recommendation=" + (.recommendation // "none"),
      "trigger_class=" + (.trigger_class // "none"),
      "experiment_run_id=" + (.experiment_run_id // "none")
    ] | .[]' "$latest_performance_receipt" | sed 's/^/  /'
fi

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
if [[ -f "$lane_health_md" ]]; then
  printf '%s\n' 'lane_health_summary:'
  sed -n '1,120p' "$lane_health_md"
fi
if [[ -f "$lane_health_json" ]]; then
  printf '%s\n' 'story_summary:'
  jq -r '
    .story
    | [
        "state=" + (.state // "unknown"),
        "eligible=" + ((.eligible // false) | tostring),
        "recovery_round=" + ((.recoveryRound // 0) | tostring),
        "accepted=" + (.acceptedState // "none"),
        "swarm_state=" + (.swarmState // "unknown"),
        "completion_audit_state=" + (.completionAuditState // "unknown"),
        "last_receipt=" + (.lastReceiptId // "none"),
        "decision=" + (.lastReceiptDecision // "none"),
        "promotion=" + (.promotionStatus // "none"),
        "path_exhausted=" + ((.pathExhausted // false) | tostring),
        "next_eligible=" + (.nextEligibleStoryId // "none"),
        "last_completion_audit_receipt=" + (.lastCompletionAuditReceiptId // "none"),
        "last_finder_audit_id=" + (.lastFinderAuditId // "none"),
        "next_action=" + (.lastReceiptNextAction // "none")
      ]
    | .[]
  ' "$lane_health_json"
  printf '%s\n' 'latest_receipt_contradictions:'
  jq -r '.story.lastReceiptContradictionsFound[]? // empty' "$lane_health_json" | sed 's/^/  - /'
  printf '%s\n' 'latest_receipt_unresolved_risks:'
  jq -r '.story.lastReceiptUnresolvedRisks[]? // empty' "$lane_health_json" | sed 's/^/  - /'
  printf '%s\n' 'latest_receipt_promotion_targets:'
  jq -r '.story.lastReceiptPromotionTargets[]? // empty' "$lane_health_json" | sed 's/^/  - /'
fi
if [[ -f "$mailbox_current_path" ]]; then
  active_story="$(defi_swarm_active_story "$repo_root")"
  printf '%s\n' 'current_mailbox_for_active_story:'
  jq -r --arg story "$active_story" '
    [.[] | select((.storyId // "") == $story)]
    | if length == 0 then
        ["(no compacted mailbox events for active story)"]
      else
        map("[\(.ts // "unknown")] story=\(.storyId // "none") lane=\(.lane // "none") type=\(.type // "none") status=\(.status // "none") reason=\(.reason // "none")")
      end
    | .[]
  ' "$mailbox_current_path"
fi
if [[ -f "$mailbox_path" ]]; then
  printf '%s\n' 'recent_mailbox_raw:'
  tail -n 20 "$mailbox_path" || true
fi
