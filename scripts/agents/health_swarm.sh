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
lane_health_md = state_dir / "lane_health.md"
lane_health_json = state_dir / "lane_health.json"
prd = json.loads((repo_root / "prd.json").read_text())
swarm_state = str(prd.get("swarmState") or "active")
completion_audit_state = str(prd.get("completionAuditState") or "pending")
last_completion_audit_receipt_id = str(prd.get("lastCompletionAuditReceiptId") or "")
last_finder_audit_id = str(prd.get("lastFinderAuditId") or "")
active_story = prd.get("activeStoryId") or ""
shell_cmds = {"bash", "sh", "zsh", "fish"}


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

lane_specs = [
    {
        "name": "research",
        "pane_index": 0,
        "expected": [
            repo_root / ".ai" / "dropbox" / "research" / f"{active_story}__brief.md",
            repo_root / ".ai" / "dropbox" / "research" / f"{active_story}__doc_refs.json",
            repo_root / ".ai" / "dropbox" / "research" / f"{active_story}__qa.md",
        ],
        "upstream": [],
    },
    {
        "name": "architecture",
        "pane_index": 2,
        "expected": [
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__review.md",
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__contract_notes.md",
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__refinement.md",
            repo_root / ".ai" / "dropbox" / "architecture" / f"{active_story}__decision.json",
        ],
        "upstream": ["research"],
    },
    {
        "name": "builder",
        "pane_index": 1,
        "expected": [
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__delivery.md",
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__files.txt",
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__validation.txt",
            repo_root / ".ai" / "dropbox" / "build" / f"{active_story}__result.json",
        ],
        "upstream": ["research", "architecture"],
    },
    {
        "name": "writer-integrator",
        "pane_index": 3,
        "expected": [
            repo_root / ".ai" / "dropbox" / "state" / "accepted_loops.md",
            repo_root / ".ai" / "dropbox" / "state" / "rejections.md",
            repo_root / ".ai" / "dropbox" / "state" / "open_questions.md",
        ],
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


def read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


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
latest_receipt_promotion_targets = list(latest_receipt.get("promotion_targets") or []) if latest_receipt else []
latest_receipt_next_action = str(latest_receipt.get("next_action") or "") if latest_receipt else ""
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
    latest_expected_epoch = 0
    latest_expected_path = None
    missing = []
    for artifact in spec["expected"]:
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
    if spec["name"] == "writer-integrator":
        story_output_epoch = latest_receipt_epoch
        story_output_path = str(latest_receipt.get("_path")) if latest_receipt else None
        story_output_ts = latest_receipt_ts or iso_from_epoch(latest_receipt_epoch)
        story_output_kind = "receipt" if latest_receipt_epoch else None
        if latest_receipt_epoch == 0 and "acceptance receipt" not in missing:
            missing.append("acceptance receipt")

    marker_path = runtime_dir / f"{spec['name'].replace('-', '_')}__last_launch.json"
    completion_path = runtime_dir / f"{spec['name'].replace('-', '_')}__last_completion.json"
    active_path = runtime_dir / f"{spec['name'].replace('-', '_')}__active.json"
    last_launch_epoch = 0
    last_launch_ts = None
    if marker_path.exists():
        try:
            marker = json.loads(marker_path.read_text())
            if marker.get("storyId") == active_story:
                last_launch_epoch = int(marker.get("epoch", 0) or 0)
                last_launch_ts = marker.get("ts")
        except json.JSONDecodeError:
            pass

    last_completion_epoch = 0
    last_completion_ts = None
    last_completion_exit_code = None
    if completion_path.exists():
        try:
            completion = json.loads(completion_path.read_text())
            if completion.get("storyId") == active_story:
                last_completion_epoch = int(completion.get("epoch", 0) or 0)
                last_completion_ts = completion.get("ts")
                exit_code = completion.get("exitCode")
                last_completion_exit_code = int(exit_code) if exit_code is not None else None
        except json.JSONDecodeError:
            pass

    active_pid = None
    active_ts = None
    active_epoch = 0
    if active_path.exists():
        try:
            active = json.loads(active_path.read_text())
            if active.get("storyId") == active_story:
                active_pid = int(active.get("pid", 0) or 0) or None
                active_ts = active.get("ts")
                active_epoch = int(active.get("epoch", 0) or 0)
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
    for upstream_name in spec["upstream"]:
        upstream_row = next((row for row in lane_rows if row["name"] == upstream_name), None)
        if upstream_row is None:
            continue
        upstream_epoch = int(upstream_row.get("latestExpectedArtifactEpoch") or 0)
        if upstream_epoch >= upstream_latest_epoch:
            upstream_latest_epoch = upstream_epoch
            upstream_reason = upstream_name

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
    elif not active_story:
        if swarm_state == "terminal_complete" and completion_audit_state == "clean":
            status = "idle"
            reason = "no active story is set because the swarm is in terminal-complete monitoring"
        else:
            status = "idle"
            reason = "no active story is set in prd.json"
    elif spec["name"] == "writer-integrator" and not active_story_eligible and next_eligible_story and next_eligible_story != active_story:
        status = "stale"
        recommendation = "yes"
        reason = f"active story is {active_story_state}; writer-integrator should rotate to next eligible story {next_eligible_story}"
    elif not active_story_eligible and not next_eligible_story:
        status = "completed"
        reason = f"active story is {active_story_state} and no eligible stories remain"
    elif path_exhausted and spec["name"] == "builder":
        status = "blocked"
        recommendation = "no"
        reason = "architecture marked the current recovery path as exhausted; builder should not relaunch"
    elif active_story_state == "done":
        status = "completed"
        recommendation = "no"
        reason = "story is done and promoted"
    elif active_pid_alive and last_launch_epoch > (effective_output_epoch or 0):
        status = "running"
        recommendation = "no"
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
            reason = f"upstream artifacts from {upstream_reason} exist but {spec['name']} has no output yet"
        elif last_launch_epoch > 0:
            status = "failed"
            recommendation = "yes"
            reason = "lane launched but no expected artifacts were written"
        elif not spec["upstream"]:
            status = "stale"
            recommendation = "yes"
            reason = "lane has not been launched yet and is the first eligible step for the current story"
        else:
            status = "idle"
            recommendation = "no"
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
            "activeStoryId": active_story,
            "status": status,
            "restartRecommendation": recommendation,
            "reason": reason,
            "expectedArtifacts": [str(path) for path in spec["expected"]],
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
            "activePid": active_pid,
            "activeTs": active_ts,
            "activeEpoch": active_epoch or None,
            "effectiveOutputEpoch": effective_output_epoch or None,
            "effectiveOutputTs": effective_output_ts,
            "effectiveOutputKind": effective_output_kind,
            "upstreamLatestArtifactEpoch": upstream_latest_epoch or None,
            "upstreamLatestArtifactTs": iso_from_epoch(upstream_latest_epoch),
            "lastLaunchEpoch": last_launch_epoch or None,
            "lastLaunchTs": last_launch_ts,
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
        "lastCompletionAuditReceiptId": last_completion_audit_receipt_id or None,
        "lastFinderAuditId": last_finder_audit_id or None,
        "lastReceiptId": last_receipt_id,
        "lastReceiptDecision": last_receipt_decision,
        "promotionStatus": last_promotion_status,
        "lastReceiptContradictionsFound": latest_receipt_contradictions,
        "lastReceiptUnresolvedRisks": latest_receipt_risks,
        "lastReceiptPromotionTargets": latest_receipt_promotion_targets,
        "lastReceiptNextAction": latest_receipt_next_action or None,
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
    f"- Last completion audit receipt: `{last_completion_audit_receipt_id or 'none'}`",
    f"- Last finder audit id: `{last_finder_audit_id or 'none'}`",
    f"- Last receipt: `{last_receipt_id or 'none'}`",
    f"- Last receipt decision: `{last_receipt_decision or 'none'}`",
    f"- Promotion status: `{last_promotion_status or 'none'}`",
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
if latest_receipt_promotion_targets:
    md_lines.append("- Receipt promotion targets:")
    for item in latest_receipt_promotion_targets:
        md_lines.append(f"  - {item}")
    md_lines.append("")
if latest_receipt_next_action:
    md_lines.append(f"- Receipt next action: `{latest_receipt_next_action}`")
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
            }
            mailbox.write(json.dumps(event) + "\n")
PY

if [[ "$quiet" != "true" ]]; then
  cat "$(defi_swarm_lane_health_md_path "$repo_root")"
fi
