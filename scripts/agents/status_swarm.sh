#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

repo="${PWD}"
session_name=""
refresh="false"

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
    --refresh)
      refresh="true"
      shift
      ;;
    -h|--help)
      printf 'Usage: status_swarm.sh [--repo PATH] [--session NAME] [--refresh]\n'
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
if [[ "$refresh" == "true" ]]; then
  "$script_dir/health_swarm.sh" --repo "$repo_root" --session "$session_name" --no-mail --quiet >/dev/null
fi

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
story_promotion_receipt_path="$(defi_swarm_story_promotion_receipt_path "$repo_root")"
research_proposal_review_receipt_path="$(defi_swarm_research_proposal_review_receipt_path "$repo_root")"

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
        "current_scope=" + (.currentScope // "none"),
        "current_mode=" + (.currentMode // "unknown"),
        "pending_trigger_type=" + (.pendingTriggerType // "none"),
        "pending_trigger_scope=" + (.pendingTriggerScope // "none"),
        "pending_trigger_story=" + (.pendingTriggerStoryId // "none"),
        "last_receipt=" + (.lastReceiptId // "none"),
        "decision=" + (.lastReceiptDecision // "none"),
        "promotion=" + (.promotionStatus // "none"),
        "last_receipt_owner_layer=" + (.lastReceiptOwnerLayer // "none"),
        "last_receipt_stage=" + (.lastReceiptStage // "none"),
        "docs_sync_state=" + (.docsSyncState // "none"),
        "docs_sync_story=" + (.docsSyncStoryId // "none"),
        "docs_truth_receipt=" + (.docsTruthReceiptId // "none"),
        "docs_truth_contradictions=" + ((.docsTruthContradictionCount // 0) | tostring),
        "story_promotion_receipt=" + (.storyPromotionReceiptId // "none"),
        "story_promotion_stage=" + (.storyPromotionStage // "none"),
        "story_promotion_owner_layer=" + (.storyPromotionOwnerLayer // "none"),
        "research_proposal_review_receipt=" + (.researchProposalReviewReceiptId // "none"),
        "research_proposal_review_status=" + (.researchProposalReviewStatus // "none"),
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
  printf '%s\n' 'latest_receipt_missing_capabilities:'
  jq -r '.story.lastReceiptMissingCapabilities[]? // empty' "$lane_health_json" | sed 's/^/  - /'
  printf '%s\n' 'latest_receipt_promotion_targets:'
  jq -r '.story.lastReceiptPromotionTargets[]? // empty' "$lane_health_json" | sed 's/^/  - /'
fi
if [[ -f "$story_promotion_receipt_path" ]]; then
  printf '%s\n' 'story_promotion_summary:'
  jq -r '
    [
      "receipt_id=" + (.receipt_id // "none"),
      "story_id=" + (.story_id // "none"),
      "stage=" + (.stage // "none"),
      "owner_layer=" + (.owner_layer // "none"),
      "north_star_link=" + (.north_star_link // "none"),
      "summary=" + (.summary // "none")
    ] | .[]' "$story_promotion_receipt_path" | sed 's/^/  /'
  printf '%s\n' 'story_promotion_created:'
  jq -r '.stories_created[]? // empty' "$story_promotion_receipt_path" | sed 's/^/  - /'
  printf '%s\n' 'story_promotion_updated:'
  jq -r '.stories_updated[]? // empty' "$story_promotion_receipt_path" | sed 's/^/  - /'
  printf '%s\n' 'story_promotion_deferred:'
  jq -r '.deferred_items[]? // empty' "$story_promotion_receipt_path" | sed 's/^/  - /'
fi
if [[ -f "$research_proposal_review_receipt_path" ]]; then
  printf '%s\n' 'research_proposal_review_summary:'
  jq -r '
    [
      "receipt_id=" + (.receipt_id // "none"),
      "source_story_id=" + (.source_story_id // "none"),
      "target_story_id=" + (.target_story_id // "none"),
      "proposal_id=" + (.proposal_id // "none"),
      "status=" + (.status // "none"),
      "story_class=" + (.story_class // "none"),
      "stage=" + (.stage // "none"),
      "summary=" + (.summary // "none")
    ] | .[]' "$research_proposal_review_receipt_path" | sed 's/^/  /'
fi
if [[ -f "$mailbox_current_path" ]]; then
  active_story="$(jq -r '.activeStoryId // ""' "$lane_health_json" 2>/dev/null || true)"
  current_scope="$(jq -r '.story.currentScope // ""' "$lane_health_json" 2>/dev/null || true)"
  current_mode="$(jq -r '.story.currentMode // "story"' "$lane_health_json" 2>/dev/null || true)"
  if [[ -n "$current_scope" && "$current_mode" != "story" ]]; then
    printf '%s\n' "current_mailbox_for_scope: $current_scope"
    jq -r --arg scope "$current_scope" '
    [.[] | select((.scope // "") == $scope)]
    | if length == 0 then
        ["(no compacted mailbox events for current scope)"]
      else
        map("[\(.ts // "unknown")] scope=\(.scope // "none") mode=\(.mode // "none") story=\(.storyId // "none") lane=\(.lane // "none") type=\(.type // "none") status=\(.status // "none") reason=\(.reason // "none")")
      end
    | .[]
  ' "$mailbox_current_path"
  else
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
fi
if [[ -f "$mailbox_path" ]]; then
  printf '%s\n' 'recent_mailbox_raw:'
  tail -n 20 "$mailbox_path" || true
fi
