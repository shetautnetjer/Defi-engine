#!/usr/bin/env bash

set -euo pipefail

defi_swarm_repo_root() {
  local repo="${1:-$PWD}"
  git -C "$repo" rev-parse --show-toplevel 2>/dev/null || (cd "$repo" && pwd -P)
}

defi_swarm_session_name() {
  printf '%s\n' "${DEFI_SWARM_SESSION_NAME:-defi-engine-swarm}"
}

defi_swarm_project_id() {
  printf '%s\n' "${DEFI_SWARM_PROJECT_ID:-defi-engine}"
}

defi_swarm_tmux_root() {
  printf '%s\n' "/home/netjer/Projects/AI-Frame/muscles/skills/tmux-lanes/scripts"
}

defi_swarm_codex_runner() {
  printf '%s\n' "/home/netjer/Projects/AI-Frame/muscles/skills/codex-cli/scripts/codex_run.sh"
}

defi_swarm_lane_number() {
  case "${1:?lane name required}" in
    research) printf '1\n' ;;
    builder) printf '2\n' ;;
    architecture) printf '3\n' ;;
    writer|writer-integrator|writer_integrator) printf '4\n' ;;
    all) printf 'all\n' ;;
    *)
      printf 'unknown lane: %s\n' "$1" >&2
      return 1
      ;;
  esac
}

defi_swarm_lane_name() {
  case "${1:?lane number required}" in
    1) printf 'research\n' ;;
    2) printf 'builder\n' ;;
    3) printf 'architecture\n' ;;
    4) printf 'writer-integrator\n' ;;
    *)
      printf 'unknown lane number: %s\n' "$1" >&2
      return 1
      ;;
  esac
}

defi_swarm_prompt_file() {
  local repo_root="${1:?repo root required}"
  local lane="${2:?lane required}"
  case "$lane" in
    research) printf '%s/.ai/templates/research.md\n' "$repo_root" ;;
    builder) printf '%s/.ai/templates/builder.md\n' "$repo_root" ;;
    architecture) printf '%s/.ai/templates/architecture.md\n' "$repo_root" ;;
    writer|writer-integrator|writer_integrator) printf '%s/.ai/templates/writer_integrator.md\n' "$repo_root" ;;
    *)
      printf 'unknown lane for prompt file: %s\n' "$lane" >&2
      return 1
      ;;
  esac
}

defi_swarm_require_repo_files() {
  local repo_root="${1:?repo root required}"
  local required=(
    "$repo_root/prd.json"
    "$repo_root/progress.txt"
    "$repo_root/.ai/agents/common.md"
    "$repo_root/.ai/index/current_repo_map.md"
  )
  local path
  for path in "${required[@]}"; do
    if [[ ! -f "$path" ]]; then
      printf 'defi-swarm: required file missing: %s\n' "$path" >&2
      return 1
    fi
  done
}

defi_swarm_normalize_completion_audit_writer() {
  local path="${1:?writer completion audit path required}"
  [[ -f "$path" ]] || return 0

  python - "$path" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    doc = json.loads(path.read_text())
except json.JSONDecodeError:
    raise SystemExit(0)

if not isinstance(doc, dict):
    raise SystemExit(0)

changed = False
audited_at = str(doc.get("audited_at") or "")

defaults = {
    "status": "",
    "promoted_story_ids": [],
    "deferred_story_ids": [],
    "rationale": [],
    "audited_at": audited_at,
}

for key, value in defaults.items():
    if doc.get(key) is None:
        doc[key] = value
        changed = True

audit_id = str(doc.get("audit_id") or "")
if not audit_id:
    if audited_at:
        doc["audit_id"] = f"completion_audit_writer::{audited_at}"
    else:
        doc["audit_id"] = ""
    changed = True

if changed:
    path.write_text(json.dumps(doc, indent=2) + "\n")
PY
}

defi_swarm_bootstrap_runtime_dirs() {
  local repo_root="${1:?repo root required}"
  mkdir -p \
    "$repo_root/.ai/dropbox/research" \
    "$repo_root/.ai/dropbox/build" \
    "$repo_root/.ai/dropbox/architecture" \
    "$repo_root/.ai/dropbox/state" \
    "$repo_root/.ai/dropbox/state/accepted_receipts" \
    "$repo_root/.ai/dropbox/state/performance_receipts" \
    "$repo_root/.ai/dropbox/state/runtime"

  local mailbox lane_health_md lane_health_json accepted_loops rejections open_questions
  local mailbox_current finder_state finder_decision completion_audit_writer
  local auto_commit_state
  mailbox="$(defi_swarm_mailbox_path "$repo_root")"
  mailbox_current="$(defi_swarm_mailbox_current_path "$repo_root")"
  lane_health_md="$(defi_swarm_lane_health_md_path "$repo_root")"
  lane_health_json="$(defi_swarm_lane_health_json_path "$repo_root")"
  accepted_loops="$repo_root/.ai/dropbox/state/accepted_loops.md"
  rejections="$repo_root/.ai/dropbox/state/rejections.md"
  open_questions="$repo_root/.ai/dropbox/state/open_questions.md"
  finder_state="$(defi_swarm_finder_state_path "$repo_root")"
  finder_decision="$(defi_swarm_finder_decision_path "$repo_root")"
  completion_audit_writer="$repo_root/.ai/dropbox/state/completion_audit_writer.json"
  auto_commit_state="$(defi_swarm_auto_commit_state_path "$repo_root")"
  [[ -f "$mailbox" ]] || : > "$mailbox"
  [[ -f "$mailbox_current" ]] || printf '%s\n' '[]' > "$mailbox_current"
  [[ -f "$lane_health_md" ]] || cat <<'EOF' > "$lane_health_md"
# Lane Health

No health check has been recorded yet.
EOF
  [[ -f "$lane_health_json" ]] || printf '%s\n' '{"generatedAt":null,"activeStoryId":null,"lanes":[]}' > "$lane_health_json"
  [[ -f "$accepted_loops" ]] || printf '# Accepted Loops\n\n' > "$accepted_loops"
  [[ -f "$rejections" ]] || printf '# Rejections\n\n' > "$rejections"
  [[ -f "$open_questions" ]] || printf '# Open Questions\n\n' > "$open_questions"
  [[ -f "$finder_state" ]] || cat <<'EOF' > "$finder_state"
{
  "pendingTrigger": null,
  "queuedReceiptFollowons": [],
  "lastProcessedReceiptId": "",
  "lastProcessedFailureSignature": "",
  "lastProcessedCompletionScope": "",
  "lastProcessedPerformanceReceiptId": "",
  "lastTerminalAuditAt": "",
  "lastFinderAuditId": "",
  "lastWriterDecisionId": ""
}
EOF
  [[ -f "$finder_decision" ]] || printf '%s\n' '{"decision_id":"","scope":"","status":"none","promoted_story_ids":[],"deferred_story_ids":[],"rationale":"","decided_at":""}' > "$finder_decision"
  defi_swarm_normalize_completion_audit_writer "$completion_audit_writer"
  if [[ ! -f "$auto_commit_state" ]]; then
    local latest_receipt_id=""
    latest_receipt_id="$(python - "$repo_root/.ai/dropbox/state/accepted_receipts" <<'PY'
from pathlib import Path
import json
import sys

receipts_dir = Path(sys.argv[1])
matches = sorted(receipts_dir.glob("*.json"))
if not matches:
    print("")
    raise SystemExit(0)
doc = json.loads(matches[-1].read_text())
print(str(doc.get("receipt_id") or ""))
PY
)"
    jq -nc \
      --arg receiptId "$latest_receipt_id" \
      --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '{lastAutoCommitReceiptId:$receiptId, lastCommitSha:"", updatedAt:$ts}' > "$auto_commit_state"
  fi
}

defi_swarm_active_story() {
  local repo_root="${1:?repo root required}"
  jq -r '.activeStoryId' "$repo_root/prd.json"
}

defi_swarm_print_lane_map() {
  cat <<'EOF'
lane-1: research
lane-2: builder
lane-3: architecture
lane-4: writer-integrator
EOF
}

defi_swarm_dropbox_dir() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$repo_root/.ai/dropbox"
}

defi_swarm_state_dir() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_dropbox_dir "$repo_root")/state"
}

defi_swarm_accepted_receipts_dir() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/accepted_receipts"
}

defi_swarm_performance_receipts_dir() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/performance_receipts"
}

defi_swarm_runtime_state_dir() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/runtime"
}

defi_swarm_supervisor_pid_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/persistent_cycle.pid"
}

defi_swarm_supervisor_log_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/persistent_cycle.log"
}

defi_swarm_supervisor_launch_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/persistent_cycle_launch.json"
}

defi_swarm_supervisor_heartbeat_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/persistent_cycle_heartbeat.json"
}

defi_swarm_supervisor_last_exit_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/persistent_cycle_last_exit.json"
}

defi_swarm_pid_is_running() {
  local pid="${1:-}"
  [[ -n "$pid" ]] || return 1
  [[ "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

defi_swarm_mailbox_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/mailbox.jsonl"
}

defi_swarm_mailbox_current_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/mailbox_current.json"
}

defi_swarm_lane_health_md_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/lane_health.md"
}

defi_swarm_lane_health_json_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/lane_health.json"
}

defi_swarm_finder_state_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/finder_state.json"
}

defi_swarm_finder_decision_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_state_dir "$repo_root")/finder_decision.json"
}

defi_swarm_auto_commit_state_path() {
  local repo_root="${1:?repo root required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/auto_commit_state.json"
}

defi_swarm_story_field() {
  local repo_root="${1:?repo root required}"
  local story_id="${2:?story id required}"
  local field="${3:?field required}"
  jq -r --arg story_id "$story_id" --arg field "$field" '
    .userStories[]
    | select(.id == $story_id)
    | .[$field]
  ' "$repo_root/prd.json"
}

defi_swarm_story_state() {
  local repo_root="${1:?repo root required}"
  local story_id="${2:?story id required}"
  jq -r --arg story_id "$story_id" '
    .userStories[]
    | select(.id == $story_id)
    | if has("state") then .state
      elif (.passes // false) then "done"
      else "ready"
      end
  ' "$repo_root/prd.json"
}

defi_swarm_story_recovery_round() {
  local repo_root="${1:?repo root required}"
  local story_id="${2:?story id required}"
  jq -r --arg story_id "$story_id" '
    .userStories[]
    | select(.id == $story_id)
    | (.recovery_round // 0)
  ' "$repo_root/prd.json"
}

defi_swarm_story_is_eligible() {
  local repo_root="${1:?repo root required}"
  local story_id="${2:?story id required}"
  case "$(defi_swarm_story_state "$repo_root" "$story_id")" in
    ready|active|recovery) return 0 ;;
    *) return 1 ;;
  esac
}

defi_swarm_next_eligible_story() {
  local repo_root="${1:?repo root required}"
  jq -r '
    .userStories
    | map(
        . + {
          state_norm:
            (if has("state") then .state
             elif (.passes // false) then "done"
             else "ready"
             end)
        }
      )
    | map(select(.state_norm == "ready" or .state_norm == "active" or .state_norm == "recovery"))
    | sort_by(.priority, .id)
    | (.[0].id // "")
  ' "$repo_root/prd.json"
}

defi_swarm_has_eligible_stories() {
  local repo_root="${1:?repo root required}"
  [[ -n "$(defi_swarm_next_eligible_story "$repo_root")" ]]
}

defi_swarm_default_model_for_lane() {
  case "${1:?lane required}" in
    builder) printf 'gpt-5.4\n' ;;
    architecture|writer|writer-integrator|writer_integrator) printf 'gpt-5.4\n' ;;
    *) printf '\n' ;;
  esac
}

defi_swarm_latest_receipt_path() {
  local repo_root="${1:?repo root required}"
  local story_id="${2:?story id required}"
  local receipts_dir
  receipts_dir="$(defi_swarm_accepted_receipts_dir "$repo_root")"
  python - "$receipts_dir" "$story_id" <<'PY'
from pathlib import Path
import sys

receipts_dir = Path(sys.argv[1])
story_id = sys.argv[2]
matches = sorted(receipts_dir.glob(f"*__{story_id}.json"))
print(matches[-1] if matches else "")
PY
}

defi_swarm_lane_slug() {
  case "${1:?lane required}" in
    research) printf 'research\n' ;;
    builder) printf 'builder\n' ;;
    architecture) printf 'architecture\n' ;;
    writer|writer-integrator|writer_integrator) printf 'writer_integrator\n' ;;
    *)
      printf 'unknown lane slug: %s\n' "$1" >&2
      return 1
      ;;
  esac
}

defi_swarm_lane_launch_marker_path() {
  local repo_root="${1:?repo root required}"
  local lane="${2:?lane required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/$(defi_swarm_lane_slug "$lane")__last_launch.json"
}

defi_swarm_lane_completion_marker_path() {
  local repo_root="${1:?repo root required}"
  local lane="${2:?lane required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/$(defi_swarm_lane_slug "$lane")__last_completion.json"
}

defi_swarm_lane_active_marker_path() {
  local repo_root="${1:?repo root required}"
  local lane="${2:?lane required}"
  printf '%s\n' "$(defi_swarm_runtime_state_dir "$repo_root")/$(defi_swarm_lane_slug "$lane")__active.json"
}

defi_swarm_lane_expected_artifacts() {
  local repo_root="${1:?repo root required}"
  local lane="${2:?lane required}"
  local story_id="${3:?story id required}"
  case "$lane" in
    research)
      printf '%s\n' \
        "$repo_root/.ai/dropbox/research/${story_id}__brief.md" \
        "$repo_root/.ai/dropbox/research/${story_id}__doc_refs.json" \
        "$repo_root/.ai/dropbox/research/${story_id}__qa.md"
      ;;
    builder)
      printf '%s\n' \
        "$repo_root/.ai/dropbox/build/${story_id}__delivery.md" \
        "$repo_root/.ai/dropbox/build/${story_id}__files.txt" \
        "$repo_root/.ai/dropbox/build/${story_id}__validation.txt" \
        "$repo_root/.ai/dropbox/build/${story_id}__result.json"
      ;;
    architecture)
      printf '%s\n' \
        "$repo_root/.ai/dropbox/architecture/${story_id}__review.md" \
        "$repo_root/.ai/dropbox/architecture/${story_id}__contract_notes.md" \
        "$repo_root/.ai/dropbox/architecture/${story_id}__refinement.md" \
        "$repo_root/.ai/dropbox/architecture/${story_id}__decision.json"
      ;;
    writer|writer-integrator|writer_integrator)
      printf '%s\n' \
        "$repo_root/.ai/dropbox/state/accepted_loops.md" \
        "$repo_root/.ai/dropbox/state/rejections.md" \
        "$repo_root/.ai/dropbox/state/open_questions.md"
      ;;
    *)
      printf 'unknown lane for expected artifacts: %s\n' "$lane" >&2
      return 1
      ;;
  esac
}

defi_swarm_append_mailbox_event() {
  local repo_root="${1:?repo root required}"
  local event_type="${2:?event type required}"
  local lane="${3:?lane required}"
  local story_id="${4:-}"
  local session_name="${5:-}"
  local status="${6:-}"
  local previous_status="${7:-}"
  local recommendation="${8:-}"
  local reason="${9:-}"
  local mailbox
  local mailbox_current
  mailbox="$(defi_swarm_mailbox_path "$repo_root")"
  mailbox_current="$(defi_swarm_mailbox_current_path "$repo_root")"
  jq -nc \
    --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg type "$event_type" \
    --arg lane "$lane" \
    --arg storyId "$story_id" \
    --arg session "$session_name" \
    --arg status "$status" \
    --arg previousStatus "$previous_status" \
    --arg recommendation "$recommendation" \
    --arg reason "$reason" \
    '{
      ts: $ts,
      type: $type,
      lane: $lane,
      storyId: ($storyId | select(length > 0)),
      session: ($session | select(length > 0)),
      status: ($status | select(length > 0)),
      previousStatus: ($previousStatus | select(length > 0)),
      recommendation: ($recommendation | select(length > 0)),
      reason: ($reason | select(length > 0))
    }' >> "$mailbox"
  python - "$mailbox" "$mailbox_current" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

mailbox = Path(sys.argv[1])
current_path = Path(sys.argv[2])
latest: dict[tuple[str, str, str], dict[str, object]] = {}

for raw in mailbox.read_text().splitlines():
    raw = raw.strip()
    if not raw:
        continue
    try:
        doc = json.loads(raw)
    except json.JSONDecodeError:
        continue
    key = (
        str(doc.get("storyId") or ""),
        str(doc.get("lane") or ""),
        str(doc.get("type") or ""),
    )
    latest[key] = doc

current = sorted(
    latest.values(),
    key=lambda item: (
        str(item.get("storyId") or ""),
        str(item.get("lane") or ""),
        str(item.get("type") or ""),
    ),
)
current_path.write_text(json.dumps(current, indent=2) + "\n")
PY
}
