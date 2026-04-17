#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: health_swarm.sh [--repo PATH] [--session NAME] [--no-mail] [--quiet]

Refresh lane-health receipts for the Defi-engine four-lane swarm.
EOF
}

repo="${PWD}"
session_name=""
emit_mail="true"
quiet="false"

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
    --no-mail)
      emit_mail="false"
      shift
      ;;
    --quiet)
      quiet="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'health_swarm: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
session_name="${session_name:-$(defi_swarm_session_name)}"
defi_swarm_bootstrap_runtime_dirs "$repo_root"

export REPO_ROOT="$repo_root"
export SESSION_NAME="$session_name"
export EMIT_MAIL="$emit_mail"

python - <<'PY'
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(os.environ["REPO_ROOT"])
session_name = os.environ["SESSION_NAME"]
emit_mail = os.environ["EMIT_MAIL"] == "true"
state_dir = repo_root / ".ai" / "dropbox" / "state"
runtime_dir = state_dir / "runtime"
receipts_dir = state_dir / "accepted_receipts"
mailbox_path = state_dir / "mailbox.jsonl"
mailbox_current_path = state_dir / "mailbox_current.json"
lane_health_md = state_dir / "lane_health.md"
lane_health_json = state_dir / "lane_health.json"
prd = json.loads((repo_root / "prd.json").read_text())
swarm_state = str(prd.get("swarmState") or "active")
completion_audit_state = str(prd.get("completionAuditState") or "pending")
last_completion_audit_receipt_id = str(prd.get("lastCompletionAuditReceiptId") or "")
last_finder_audit_id = str(prd.get("lastFinderAuditId") or "")
active_story = prd.get("activeStoryId") or ""
shell_cmds = {"bash", "sh", "zsh", "fish"}


def read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def story_state(story: dict[str, object]) -> str:
    if "state" in story and story["state"]:
        return str(story["state"])
    return "done" if story.get("passes") else "ready"


story_rows = []
for story in prd.get("userStories", []):
    row = dict(story)
    row["state_norm"] = story_state(story)
    story_rows.append(row)
story_index = {story["id"]: story for story in story_rows}
eligible_states = {"ready", "active", "recovery"}
eligible_stories = sorted(
    [story for story in story_rows if story["state_norm"] in eligible_states],
    key=lambda item: (item.get("priority", 9999), item["id"]),
)
next_eligible_story = eligible_stories[0]["id"] if eligible_stories else None
active_story_row = story_index.get(active_story)
active_story_state = active_story_row["state_norm"] if active_story_row else ("none" if not active_story else "missing")
active_story_recovery_round = int(active_story_row.get("recovery_round", 0) or 0) if active_story_row else 0
active_story_eligible = active_story_state in eligible_states
finder_state = read_json(state_dir / "finder_state.json") or {}
docs_truth_receipt = read_json(state_dir / "docs_truth_receipt.json") or {}
docs_sync_status = read_json(state_dir / "docs_sync_status.json") or {}
story_promotion_receipt = read_json(state_dir / "story_promotion_receipt.json") or {}
pending_trigger = finder_state.get("pendingTrigger") or {}
pending_trigger_type = str(pending_trigger.get("triggerType") or "")
pending_scope = str(pending_trigger.get("scope") or "")
pending_story_id = str(pending_trigger.get("storyId") or "")
if pending_scope:
    current_scope = pending_scope
    current_mode = "completion_audit" if pending_scope == "completion_audit" else "finder"
elif active_story:
    current_scope = active_story
    current_mode = "story"
elif swarm_state == "terminal_complete" and completion_audit_state == "clean":
    current_scope = ""
    current_mode = "terminal_monitoring"
else:
    current_scope = ""
    current_mode = "idle"


def expected_artifacts_for_lane(lane_name: str) -> list[Path]:
    if current_mode in {"finder", "completion_audit"} and current_scope:
        if lane_name == "research":
            return [
                repo_root / ".ai" / "dropbox" / "research" / f"{current_scope}__research_gap_scan.md",
                repo_root / ".ai" / "dropbox" / "research" / f"{current_scope}__unknowns_and_needed_evidence.json",
                repo_root / ".ai" / "dropbox" / "research" / f"{current_scope}__followon_story_candidates.json",
            ]
        if lane_name == "architecture":
            return [
                repo_root / ".ai" / "dropbox" / "architecture" / f"{current_scope}__architecture_efficiency_audit.md",
                repo_root / ".ai" / "dropbox" / "architecture" / f"{current_scope}__subtraction_candidates.json",
                repo_root / ".ai" / "dropbox" / "architecture" / f"{current_scope}__followon_story_candidates.json",
            ]
        if lane_name == "writer-integrator":
            if current_scope == "completion_audit":
                return [state_dir / "completion_audit_writer.json"]
            return [state_dir / "finder_decision.json"]
        return []
    if lane_name == "research":
        return [
            repo_root / ".ai" / "dropbox" / "research" / f"{active_story}__brief.md",
            repo_root / ".ai" / "dropbox" / "research" / f"{active_story}__doc_refs.json",
            repo_root / ".ai" / "dropbox" / "research" / f"{active_story}__qa.md",
        ]
    if lane_name == "architecture":
        return [
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__review.md",
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__contract_notes.md",
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__refinement.md",
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__decision.json",
        ]
    if lane_name == "builder":
        return [
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__delivery.md",
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__files.txt",
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__validation.txt",
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__result.json",
        ]
    if lane_name == "writer-integrator":
        return [
            repo_root / ".ai" / "dropbox" / "state" / "accepted_loops.md",
            repo_root / ".ai" / "dropbox" / "state" / "rejections.md",
            repo_root / ".ai" / "dropbox" / "state" / "open_questions.md",
        ]
    return []


def lane_participates_in_current_mode(lane_name: str) -> bool:
    if current_mode in {"finder", "completion_audit"}:
        return lane_name in {"research", "architecture", "writer-integrator"}
    return True


def marker_matches(doc: dict[str, object]) -> bool:
    marker_scope = str(doc.get("scope") or "")
    marker_story_id = str(doc.get("storyId") or "")
    if current_mode in {"finder", "completion_audit"} and current_scope:
        if marker_scope:
            return marker_scope == current_scope
        if current_mode == "finder" and marker_story_id:
            return marker_story_id == current_scope
        return False
    if current_mode == "story" and active_story:
        return marker_story_id == active_story
    return False

lane_specs = [
    {
        "name": "research",
        "pane_index": 0,
        "upstream": [],
    },
    {
        "name": "architecture",
        "pane_index": 2,
        "upstream": ["research"],
    },
    {
        "name": "builder",
        "pane_index": 1,
        "upstream": ["research", "architecture"],
    },
    {
        "name": "writer-integrator",
        "pane_index": 3,
        "upstream": ["research", "builder", "architecture"],
    },
]


def iso_from_epoch(epoch: int | None) -> str | None:
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def path_epoch(path: Path) -> int:
    if not path.exists():
        return 0
    return int(path.stat().st_mtime)


def current_cmd(pane_index: int) -> str:
    target = f"{session_name}:lanes.{pane_index}"
    try:
        return (
            subprocess.check_output(
                ["tmux", "display-message", "-p", "-t", target, "#{pane_current_command}"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
            or "bash"
        )
    except subprocess.CalledProcessError:
        return "stopped"


def session_running() -> bool:
    return subprocess.run(
        ["tmux", "has-session", "-t", session_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def latest_story_receipt(story_id: str) -> dict[str, object] | None:
    matches = sorted(receipts_dir.glob(f"*__{story_id}.json"))
    if not matches:
        return None
    path = matches[-1]
    try:
        doc = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    doc["_path"] = str(path)
    doc["_epoch"] = int(path.stat().st_mtime)
    return doc

previous = {}
if lane_health_json.exists():
    try:
        previous_doc = json.loads(lane_health_json.read_text())
        previous = {lane["name"]: lane for lane in previous_doc.get("lanes", [])}
    except json.JSONDecodeError:
        previous = {}

running = session_running()
lane_rows: list[dict[str, object]] = []
generated_epoch = int(datetime.now(timezone.utc).timestamp())

latest_receipt = latest_story_receipt(active_story) if active_story else None
last_receipt_id = str(latest_receipt.get("receipt_id", "")) if latest_receipt else None
last_receipt_decision = str(latest_receipt.get("decision", "")) if latest_receipt else None
last_promotion_status = str(latest_receipt.get("promotion_status", "")) if latest_receipt else None
latest_receipt_epoch = int(latest_receipt.get("_epoch", 0) or 0) if latest_receipt else 0
latest_receipt_ts = (
    str(latest_receipt.get("timestamp") or latest_receipt.get("ts") or "")
    if latest_receipt
    else ""
)
latest_receipt_contradictions = list(latest_receipt.get("contradictions_found") or []) if latest_receipt else []
latest_receipt_risks = list(latest_receipt.get("unresolved_risks") or []) if latest_receipt else []
latest_receipt_missing_capabilities = list(latest_receipt.get("missing_capabilities") or []) if latest_receipt else []
latest_receipt_promotion_targets = list(latest_receipt.get("promotion_targets") or []) if latest_receipt else []
latest_receipt_next_action = str(latest_receipt.get("next_action") or "") if latest_receipt else ""
latest_receipt_owner_layer = str(latest_receipt.get("owner_layer") or "") if latest_receipt else ""
latest_receipt_stage = str(latest_receipt.get("stage") or "") if latest_receipt else ""
docs_sync_state = str(docs_sync_status.get("status") or "pending")
docs_sync_story_id = str(docs_sync_status.get("storyId") or "")
docs_truth_receipt_id = str(docs_truth_receipt.get("receipt_id") or "")
docs_truth_contradictions = list(docs_truth_receipt.get("contradictions") or [])
docs_truth_contradiction_count = int(
    docs_truth_receipt.get("contradiction_count") or len(docs_truth_contradictions)
)
story_promotion_receipt_id = str(story_promotion_receipt.get("receipt_id") or "")
story_promotion_stage = str(story_promotion_receipt.get("stage") or "")
story_promotion_owner_layer = str(story_promotion_receipt.get("owner_layer") or "")
story_promotion_story_id = str(story_promotion_receipt.get("story_id") or "")
story_promotion_created = list(story_promotion_receipt.get("stories_created") or [])
story_promotion_updated = list(story_promotion_receipt.get("stories_updated") or [])
story_promotion_deferred = list(story_promotion_receipt.get("deferred_items") or [])
story_promotion_summary = str(story_promotion_receipt.get("summary") or "")
accepted_state = "none"
if active_story_state == "done" or (last_receipt_decision == "accept" and last_promotion_status == "complete"):
    accepted_state = "complete"
elif last_receipt_decision == "accept":
    accepted_state = "pending_promotion"
elif last_receipt_decision:
    accepted_state = last_receipt_decision

architecture_decision = read_json(repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__decision.json") if active_story else None
builder_result = read_json(repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__result.json") if active_story else None
path_exhausted = bool(architecture_decision.get("path_exhausted")) if architecture_decision else False
architecture_recommended_action = (
    str(architecture_decision.get("recommended_action", ""))
    if architecture_decision
    else ""
)

for spec in lane_specs:
    expected_artifacts = expected_artifacts_for_lane(spec["name"])
    lane_participates = lane_participates_in_current_mode(spec["name"])
    latest_expected_epoch = 0
    latest_expected_path = None
    missing = []
    for artifact in expected_artifacts:
        artifact_epoch = path_epoch(artifact)
        if artifact_epoch:
            if artifact_epoch >= latest_expected_epoch:
                latest_expected_epoch = artifact_epoch
                latest_expected_path = str(artifact)
        else:
            missing.append(artifact.name)

    story_output_epoch = latest_expected_epoch
    story_output_path = latest_expected_path
    story_output_ts = iso_from_epoch(latest_expected_epoch)
    story_output_kind = "artifact" if latest_expected_epoch else None
    if current_mode == "story" and spec["name"] == "writer-integrator":
        docs_clean_for_active_story = (
            docs_sync_state == "clean"
            and active_story
            and docs_sync_story_id == active_story
        )
        story_output_epoch = latest_receipt_epoch if docs_clean_for_active_story else 0
        story_output_path = str(latest_receipt.get("_path")) if latest_receipt else None
        story_output_ts = latest_receipt_ts or iso_from_epoch(latest_receipt_epoch)
        story_output_kind = "receipt" if latest_receipt_epoch else None
        if latest_receipt_epoch == 0 and "acceptance receipt" not in missing:
            missing.append("acceptance receipt")
        if not docs_clean_for_active_story and "docs truth receipt" not in missing:
            missing.append("docs truth receipt")

    marker_path = runtime_dir / f"{spec['name'].replace('-', '_')}__last_launch.json"
    completion_path = runtime_dir / f"{spec['name'].replace('-', '_')}__last_completion.json"
    active_path = runtime_dir / f"{spec['name'].replace('-', '_')}__active.json"
    heartbeat_path = runtime_dir / f"{spec['name'].replace('-', '_')}__heartbeat.json"
    last_launch_epoch = 0
    last_launch_ts = None
    last_launch_scope = ""
    last_launch_mode = ""
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text())
            if marker_matches(marker):
                last_launch_epoch = int(marker.get("epoch", 0) or 0)
                last_launch_ts = marker.get("ts")
                last_launch_scope = str(marker.get("scope") or "")
                last_launch_mode = str(marker.get("mode") or "")
        except json.JSONDecodeError:
            pass

    last_completion_epoch = 0
    last_completion_ts = None
    last_completion_exit_code = None
    last_completion_scope = ""
    last_completion_mode = ""
    if completion_path.exists():
        try:
            completion = json.loads(completion_path.read_text())
            if marker_matches(completion):
                last_completion_epoch = int(completion.get("epoch", 0) or 0)
                last_completion_ts = completion.get("ts")
                exit_code = completion.get("exitCode")
                last_completion_exit_code = int(exit_code) if exit_code is not None else None
                last_completion_scope = str(completion.get("scope") or "")
                last_completion_mode = str(completion.get("mode") or "")
        except json.JSONDecodeError:
            pass

    active_pid = None
    active_ts = None
    active_epoch = 0
    active_story_id = None
    active_scope = ""
    active_mode = ""
    active_prompt_file = None
    active_prompt_type = None
    active_started_at = None
    if active_path.exists():
        try:
            active = json.loads(active_path.read_text())
            active_story_id = str(active.get("storyId") or "")
            active_scope = str(active.get("scope") or "")
            active_mode = str(active.get("mode") or "")
            active_prompt_file = str(active.get("promptFile") or "")
            active_prompt_type = str(active.get("promptType") or "")
            active_started_at = active.get("startedAt") or active.get("ts")
            active_pid = int(active.get("pid", 0) or 0) or None
            active_ts = active.get("ts")
            active_epoch = int(active.get("epoch", 0) or 0)
        except json.JSONDecodeError:
            pass
    active_heartbeat_ts = None
    active_heartbeat_epoch = 0
    if heartbeat_path.exists():
        try:
            heartbeat = json.loads(heartbeat_path.read_text())
            active_heartbeat_ts = heartbeat.get("ts")
            active_heartbeat_epoch = int(heartbeat.get("epoch", 0) or 0)
        except json.JSONDecodeError:
            pass
    active_pid_alive = False
    if active_pid:
        try:
            os.kill(active_pid, 0)
            active_pid_alive = True
        except OSError:
            active_pid_alive = False

    pane_command = current_cmd(spec["pane_index"]) if running else "stopped"
    alive = running and pane_command != "stopped"
    upstream_latest_epoch = 0
    upstream_reason = ""
    upstream_kind = ""
    for upstream_name in spec["upstream"]:
        upstream_row = next((row for row in lane_rows if row["name"] == upstream_name), None)
        if upstream_row is None:
            continue
        upstream_epoch = int(
            upstream_row.get("effectiveOutputEpoch")
            or upstream_row.get("latestExpectedArtifactEpoch")
            or 0
        )
        if upstream_epoch >= upstream_latest_epoch:
            upstream_latest_epoch = upstream_epoch
            upstream_reason = upstream_name
            upstream_kind = str(upstream_row.get("effectiveOutputKind") or "")

    status = "idle"
    recommendation = "no"
    reason = "lane has not been launched for current story"
    effective_output_epoch = story_output_epoch
    effective_output_ts = story_output_ts
    effective_output_kind = story_output_kind
    if (
        spec["name"] != "writer-integrator"
        and last_completion_exit_code == 0
        and last_completion_epoch >= latest_expected_epoch
    ):
        effective_output_epoch = last_completion_epoch
        effective_output_ts = last_completion_ts
        effective_output_kind = "completion"
    if not running:
        status = "stopped"
        reason = "tmux session is not running"
    elif not active_story and current_mode not in {"finder", "completion_audit"}:
        if swarm_state == "terminal_complete" and completion_audit_state == "clean":
            status = "idle"
            reason = "no active story is set because the swarm is in terminal-complete monitoring"
        else:
            status = "idle"
            reason = "no active story is set in prd.json"
    elif current_mode in {"finder", "completion_audit"} and not lane_participates:
        status = "idle"
        recommendation = "no"
        reason = f"{spec['name']} is parked while {current_scope or current_mode} scoped work is active"
    elif current_mode == "story" and spec["name"] == "writer-integrator" and not active_story_eligible and next_eligible_story and next_eligible_story != active_story:
        status = "stale"
        recommendation = "yes"
        reason = f"active story is {active_story_state}; writer-integrator should rotate to next eligible story {next_eligible_story}"
    elif current_mode == "story" and not active_story_eligible and not next_eligible_story:
        status = "completed"
        reason = f"active story is {active_story_state} and no eligible stories remain"
    elif current_mode == "story" and path_exhausted and spec["name"] == "builder":
        status = "blocked"
        recommendation = "no"
        reason = "architecture marked the current recovery path as exhausted; builder should not relaunch"
    elif current_mode == "story" and active_story_state == "done":
        status = "completed"
        recommendation = "no"
        reason = "story is done and promoted"
    elif active_pid_alive and current_mode in {"finder", "completion_audit"} and not active_scope:
        status = "failed"
        recommendation = "yes"
        reason = "lane process is still alive without a scope-scoped active marker contract"
    elif active_pid_alive and current_mode in {"finder", "completion_audit"} and active_scope != current_scope:
        status = "failed"
        recommendation = "yes"
        reason = f"lane process is still alive for scope {active_scope or 'none'} instead of {current_scope}"
    elif active_pid_alive and current_mode in {"finder", "completion_audit"} and active_mode and active_mode != current_mode:
        status = "failed"
        recommendation = "yes"
        reason = f"lane process is still alive in mode {active_mode} instead of {current_mode}"
    elif active_pid_alive and current_mode == "story" and not active_story_id:
        status = "failed"
        recommendation = "yes"
        reason = "lane process is still alive without a story-scoped active marker contract"
    elif active_pid_alive and current_mode == "story" and active_story_id != active_story:
        status = "failed"
        recommendation = "yes"
        reason = f"lane process is still alive for story {active_story_id} instead of {active_story}"
    elif active_pid_alive and last_launch_epoch > (effective_output_epoch or 0):
        status = "running"
        recommendation = "no"
        if current_mode in {"finder", "completion_audit"}:
            reason = "lane process is still alive for the current scope"
        else:
            reason = "lane process is still alive for the current story"
    elif effective_output_epoch == 0:
        if (
            last_launch_epoch > 0
            and last_completion_epoch < last_launch_epoch
            and generated_epoch - last_launch_epoch <= 300
        ):
            status = "running"
            recommendation = "no"
            reason = "lane launched and is still within the post-launch grace window"
        elif upstream_latest_epoch > 0:
            status = "stale"
            recommendation = "yes"
            if upstream_kind == "completion":
                reason = f"upstream completion from {upstream_reason} exists but {spec['name']} has no output yet"
            else:
                reason = f"upstream artifacts from {upstream_reason} exist but {spec['name']} has no output yet"
        elif last_launch_epoch > 0:
            status = "failed"
            recommendation = "yes"
            reason = "lane launched but no expected artifacts were written"
        elif not spec["upstream"]:
            status = "stale"
            recommendation = "yes"
            if current_mode in {"finder", "completion_audit"}:
                reason = "lane has not been launched yet and is the first eligible step for the current scope"
            else:
                reason = "lane has not been launched yet and is the first eligible step for the current story"
        else:
            status = "idle"
            recommendation = "no"
            if current_mode in {"finder", "completion_audit"}:
                reason = "lane has not been launched for the current scope"
            else:
                reason = "lane has not been launched for current story"
    elif last_completion_exit_code not in (None, 0) and last_completion_epoch >= last_launch_epoch:
        status = "failed"
        recommendation = "yes"
        reason = f"lane completed with exit code {last_completion_exit_code}"
    elif (
        last_launch_epoch > effective_output_epoch
        and last_completion_epoch < last_launch_epoch
        and generated_epoch - last_launch_epoch <= 300
    ):
        status = "running"
        recommendation = "no"
        reason = "lane launch is newer than output and still within the post-launch grace window"
    elif last_launch_epoch > effective_output_epoch:
        status = "failed"
        recommendation = "yes"
        reason = "lane launch is newer than its latest completion or artifact"
    elif upstream_latest_epoch > effective_output_epoch:
        status = "stale"
        recommendation = "yes"
        if upstream_kind == "completion":
            reason = f"upstream completion from {upstream_reason} is newer than {spec['name']} output"
        else:
            reason = f"upstream artifacts from {upstream_reason} are newer than {spec['name']} output"
    else:
        status = "completed"
        recommendation = "no"
        reason = "expected artifacts are present and current"
        if effective_output_kind == "completion" and latest_expected_epoch < last_completion_epoch:
            reason = "lane completed successfully without changing expected artifacts"

    lane_rows.append(
        {
            "name": spec["name"],
            "paneIndex": spec["pane_index"],
            "paneCommand": pane_command,
            "alive": alive,
            "producingState": status,
            "acceptedState": accepted_state,
            "currentStoryId": active_story,
            "currentScope": current_scope or None,
            "currentMode": current_mode,
            "status": status,
            "restartRecommendation": recommendation,
            "reason": reason,
            "expectedArtifacts": [str(path) for path in expected_artifacts],
            "missingArtifacts": missing,
            "latestExpectedArtifact": latest_expected_path,
            "latestExpectedArtifactEpoch": latest_expected_epoch or None,
            "latestExpectedArtifactTs": iso_from_epoch(latest_expected_epoch),
            "storyScopedOutputPath": story_output_path,
            "storyScopedOutputEpoch": story_output_epoch or None,
            "storyScopedOutputTs": story_output_ts,
            "storyScopedOutputKind": story_output_kind,
            "lastCompletionEpoch": last_completion_epoch or None,
            "lastCompletionTs": last_completion_ts,
            "lastCompletionExitCode": last_completion_exit_code,
            "lastCompletionScope": last_completion_scope or None,
            "lastCompletionMode": last_completion_mode or None,
            "activePid": active_pid,
            "activeTs": active_ts,
            "activeEpoch": active_epoch or None,
            "activeStoryId": active_story_id,
            "activeScope": active_scope or None,
            "activeMode": active_mode or None,
            "activePromptFile": active_prompt_file,
            "activePromptType": active_prompt_type,
            "activeStartedAt": active_started_at,
            "activeHeartbeatTs": active_heartbeat_ts,
            "activeHeartbeatEpoch": active_heartbeat_epoch or None,
            "effectiveOutputEpoch": effective_output_epoch or None,
            "effectiveOutputTs": effective_output_ts,
            "effectiveOutputKind": effective_output_kind,
            "upstreamLatestArtifactEpoch": upstream_latest_epoch or None,
            "upstreamLatestArtifactTs": iso_from_epoch(upstream_latest_epoch),
            "lastLaunchEpoch": last_launch_epoch or None,
            "lastLaunchTs": last_launch_ts,
            "lastLaunchScope": last_launch_scope or None,
            "lastLaunchMode": last_launch_mode or None,
            "lastSuccessTs": effective_output_ts,
            "lastFailureTs": last_launch_ts if status == "failed" else None,
        }
    )

generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
doc = {
    "generatedAt": generated_at,
    "session": session_name,
    "activeStoryId": active_story,
    "story": {
        "state": active_story_state,
        "eligible": active_story_eligible,
        "recoveryRound": active_story_recovery_round,
        "nextEligibleStoryId": next_eligible_story,
        "acceptedState": accepted_state,
        "swarmState": swarm_state,
        "completionAuditState": completion_audit_state,
        "currentScope": current_scope or None,
        "currentMode": current_mode,
        "pendingTriggerType": pending_trigger_type or None,
        "pendingTriggerScope": pending_scope or None,
        "pendingTriggerStoryId": pending_story_id or None,
        "lastCompletionAuditReceiptId": last_completion_audit_receipt_id or None,
        "lastFinderAuditId": last_finder_audit_id or None,
        "lastReceiptId": last_receipt_id,
        "lastReceiptDecision": last_receipt_decision,
        "promotionStatus": last_promotion_status,
        "lastReceiptContradictionsFound": latest_receipt_contradictions,
        "lastReceiptUnresolvedRisks": latest_receipt_risks,
        "lastReceiptMissingCapabilities": latest_receipt_missing_capabilities,
        "lastReceiptPromotionTargets": latest_receipt_promotion_targets,
        "lastReceiptOwnerLayer": latest_receipt_owner_layer or None,
        "lastReceiptStage": latest_receipt_stage or None,
        "lastReceiptNextAction": latest_receipt_next_action or None,
        "docsSyncState": docs_sync_state,
        "docsSyncStoryId": docs_sync_story_id or None,
        "docsTruthReceiptId": docs_truth_receipt_id or None,
        "docsTruthContradictionCount": docs_truth_contradiction_count,
        "storyPromotionReceiptId": story_promotion_receipt_id or None,
        "storyPromotionStoryId": story_promotion_story_id or None,
        "storyPromotionStage": story_promotion_stage or None,
        "storyPromotionOwnerLayer": story_promotion_owner_layer or None,
        "storyPromotionStoriesCreated": story_promotion_created,
        "storyPromotionStoriesUpdated": story_promotion_updated,
        "storyPromotionDeferredItems": story_promotion_deferred,
        "storyPromotionSummary": story_promotion_summary or None,
        "pathExhausted": path_exhausted,
        "architectureRecommendedAction": architecture_recommended_action or None,
        "builderResult": builder_result.get("result") if builder_result else None,
    },
    "lanes": lane_rows,
}
lane_health_json.write_text(json.dumps(doc, indent=2) + "\n")

md_lines = [
    "# Lane Health",
    "",
    f"- Generated at: `{generated_at}`",
    f"- Session: `{session_name}`",
    f"- Active story: `{active_story}`",
    f"- Story state: `{active_story_state}`",
    f"- Story eligible: `{str(active_story_eligible).lower()}`",
    f"- Recovery round: `{active_story_recovery_round}`",
    f"- Accepted state: `{accepted_state}`",
    f"- Swarm state: `{swarm_state}`",
    f"- Completion audit state: `{completion_audit_state}`",
    f"- Current scope: `{current_scope or 'none'}`",
    f"- Current mode: `{current_mode}`",
    f"- Pending trigger type: `{pending_trigger_type or 'none'}`",
    f"- Pending trigger scope: `{pending_scope or 'none'}`",
    f"- Pending trigger story: `{pending_story_id or 'none'}`",
    f"- Last completion audit receipt: `{last_completion_audit_receipt_id or 'none'}`",
    f"- Last finder audit id: `{last_finder_audit_id or 'none'}`",
    f"- Last receipt: `{last_receipt_id or 'none'}`",
    f"- Last receipt decision: `{last_receipt_decision or 'none'}`",
    f"- Promotion status: `{last_promotion_status or 'none'}`",
    f"- Last receipt owner layer: `{latest_receipt_owner_layer or 'none'}`",
    f"- Last receipt stage: `{latest_receipt_stage or 'none'}`",
    f"- Docs sync state: `{docs_sync_state}`",
    f"- Docs sync story: `{docs_sync_story_id or 'none'}`",
    f"- Docs truth receipt: `{docs_truth_receipt_id or 'none'}`",
    f"- Docs truth contradictions: `{docs_truth_contradiction_count}`",
    f"- Story promotion receipt: `{story_promotion_receipt_id or 'none'}`",
    f"- Story promotion story: `{story_promotion_story_id or 'none'}`",
    f"- Story promotion stage: `{story_promotion_stage or 'none'}`",
    f"- Story promotion owner layer: `{story_promotion_owner_layer or 'none'}`",
    f"- Next eligible story: `{next_eligible_story or 'none'}`",
    f"- Architecture path exhausted: `{str(path_exhausted).lower()}`",
    "",
]
if latest_receipt_contradictions:
    md_lines.append("- Receipt contradictions found:")
    for item in latest_receipt_contradictions:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if latest_receipt_risks:
    md_lines.append("- Receipt unresolved risks:")
    for item in latest_receipt_risks:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if latest_receipt_missing_capabilities:
    md_lines.append("- Receipt missing capabilities:")
    for item in latest_receipt_missing_capabilities:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if latest_receipt_promotion_targets:
    md_lines.append("- Receipt promotion targets:")
    for item in latest_receipt_promotion_targets:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if latest_receipt_next_action:
    md_lines.append(f"- Receipt next action: `{latest_receipt_next_action}`")
    md_lines.append("")
if story_promotion_created:
    md_lines.append("- Story promotion created:")
    for item in story_promotion_created:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if story_promotion_updated:
    md_lines.append("- Story promotion updated:")
    for item in story_promotion_updated:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if story_promotion_deferred:
    md_lines.append("- Story promotion deferred:")
    for item in story_promotion_deferred:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if story_promotion_summary:
    md_lines.append(f"- Story promotion summary: `{story_promotion_summary}`")
    md_lines.append("")
for row in lane_rows:
    md_lines.extend(
        [
            f"## {row['name']}",
            "",
            f"- alive: `{str(row['alive']).lower()}`",
            f"- pane command: `{row['paneCommand']}`",
            f"- producing: `{row['producingState']}`",
            f"- accepted: `{row['acceptedState']}`",
            f"- restart recommendation: `{row['restartRecommendation']}`",
            f"- last launch: `{row['lastLaunchTs'] or 'none'}`",
            f"- active pid: `{row['activePid'] or 'none'}`",
            f"- active story id: `{row['activeStoryId'] or 'none'}`",
            f"- active scope: `{row['activeScope'] or 'none'}`",
            f"- active mode: `{row['activeMode'] or 'none'}`",
            f"- active prompt type: `{row['activePromptType'] or 'none'}`",
            f"- active prompt file: `{row['activePromptFile'] or 'none'}`",
            f"- active started at: `{row['activeStartedAt'] or 'none'}`",
            f"- active heartbeat: `{row['activeHeartbeatTs'] or 'none'}`",
            f"- last completion: `{row['lastCompletionTs'] or 'none'}`",
            f"- last success: `{row['lastSuccessTs'] or 'none'}`",
            f"- latest artifact: `{row['latestExpectedArtifact'] or 'none'}`",
            f"- missing artifacts: `{', '.join(row['missingArtifacts']) if row['missingArtifacts'] else 'none'}`",
            f"- reason: {row['reason']}",
            "",
        ]
    )
lane_health_md.write_text("\n".join(md_lines))

if emit_mail:
    changed_events = []
    with mailbox_path.open("a", encoding="utf-8") as mailbox:
        for row in lane_rows:
            prev = previous.get(row["name"], {})
            previous_status = prev.get("status")
            previous_recommendation = prev.get("restartRecommendation")
            if previous_status == row["status"] and previous_recommendation == row["restartRecommendation"]:
                continue
            event = {
                "ts": generated_at,
                "type": "lane_status",
                "lane": row["name"],
                "storyId": active_story,
                "session": session_name,
                "status": row["status"],
                "previousStatus": previous_status,
                "recommendation": row["restartRecommendation"],
                "reason": row["reason"],
                "scope": current_scope or None,
                "mode": current_mode or None,
            }
            mailbox.write(json.dumps(event) + "\n")
            changed_events.append(event)
    if changed_events:
        latest: dict[tuple[str, str, str, str], dict[str, object]] = {}
        for raw in mailbox_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                doc = json.loads(raw)
            except json.JSONDecodeError:
                continue
            key = (
                str(doc.get("storyId") or ""),
                str(doc.get("scope") or ""),
                str(doc.get("lane") or ""),
                str(doc.get("type") or ""),
            )
            latest[key] = doc
        compacted = sorted(
            latest.values(),
            key=lambda item: (
                str(item.get("storyId") or ""),
                str(item.get("scope") or ""),
                str(item.get("lane") or ""),
                str(item.get("type") or ""),
            ),
        )
        mailbox_current_path.write_text(json.dumps(compacted, indent=2) + "\n", encoding="utf-8")
PY

if [[ "$quiet" != "true" ]]; then
  cat "$(defi_swarm_lane_health_md_path "$repo_root")"
fi
