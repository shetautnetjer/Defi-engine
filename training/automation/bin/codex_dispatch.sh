#!/usr/bin/env bash
set -euo pipefail

EVENT_FILE=""
RULES_FILE=""
RECEIPTS_DIR=""
DRY_RUN=0
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
TRAINING_ROOT="$(cd -- "${AUTOMATION_ROOT}/.." && pwd)"
DEFAULT_REPO_ROOT="$(cd -- "${TRAINING_ROOT}/.." && pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-file) EVENT_FILE="$2"; shift 2 ;;
    --rules) RULES_FILE="$2"; shift 2 ;;
    --receipts-dir) RECEIPTS_DIR="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -z "${EVENT_FILE}" || -z "${RULES_FILE}" || -z "${RECEIPTS_DIR}" ]]; then
  echo "Missing required args" >&2
  exit 2
fi

mkdir -p "${RECEIPTS_DIR}"

readarray -t META < <(python3 - "$EVENT_FILE" "$RULES_FILE" "$RECEIPTS_DIR" <<'PY'
import json, pathlib, sys
event = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
rules = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
defaults = rules.get('defaults', {})
cfg = dict(defaults)
cfg.update(rules.get('event_types', {}).get(event.get('event_type', ''), {}))
event_id = event.get('event_id', 'unknown')
prefix = cfg.get('receipt_prefix', 'receipt')
receipt = pathlib.Path(sys.argv[3]) / f"{prefix}_{event_id}.md"
print(cfg.get('mode', 'suggest'))
print(cfg.get('lane_name', 'task'))
print(cfg.get('dispatch_mode', 'fresh'))
print(cfg.get('codex_profile', 'task'))
print(cfg.get('template', 'automation/prompts/generic_review.md.tmpl'))
print(str(receipt))
print(event.get('event_id', 'unknown'))
print(event.get('event_type', 'unknown'))
print(event.get('repo_root', ''))
PY
)

MODE="${META[0]}"
LANE_NAME="${META[1]}"
DISPATCH_MODE="${META[2]}"
CODEX_PROFILE="${META[3]}"
TEMPLATE="${META[4]}"
RECEIPT_PATH="${META[5]}"
EVENT_ID="${META[6]}"
EVENT_TYPE="${META[7]}"
TARGET_REPO_ROOT="${META[8]}"
if [[ -z "${TARGET_REPO_ROOT}" ]]; then
  TARGET_REPO_ROOT="${DEFAULT_REPO_ROOT}"
fi
LANE_STATE_PATH="${TARGET_REPO_ROOT}/training/automation/state/lane_sessions.json"
mkdir -p "$(dirname "${LANE_STATE_PATH}")"

TMP_PROMPT="$(mktemp)"
if [[ "${TEMPLATE}" != /* ]]; then
  TEMPLATE="${TRAINING_ROOT}/${TEMPLATE}"
fi

python3 "${SCRIPT_DIR}/render_prompt.py" \
  --event-file "${EVENT_FILE}" \
  --template "${TEMPLATE}" \
  --receipt-path "${RECEIPT_PATH}" \
  --output "${TMP_PROMPT}"

if [[ "${MODE}" == "suggest" ]]; then
  MODE_FLAGS=()
elif [[ "${MODE}" == "auto-edit" ]]; then
  MODE_FLAGS=()
elif [[ "${MODE}" == "full-auto" ]]; then
  MODE_FLAGS=(--full-auto)
else
  echo "Unknown mode: ${MODE}" >&2
  rm -f "${TMP_PROMPT}"
  exit 2
fi

CODEX_BIN="${CODEX_BIN:-codex}"
CODEX_HELP="$(${CODEX_BIN} --help 2>/dev/null || true)"
USE_EXEC=0
if echo "${CODEX_HELP}" | grep -q "exec"; then
  USE_EXEC=1
fi
USE_EXEC_RESUME=${USE_EXEC}

readarray -t SESSION_META < <(python3 - "$LANE_STATE_PATH" "$LANE_NAME" "$DISPATCH_MODE" <<'PY'
import json, pathlib, sys
from datetime import datetime, timezone

lane_state_path = pathlib.Path(sys.argv[1])
lane_name = sys.argv[2]
dispatch_mode = sys.argv[3]
now = datetime.now(timezone.utc)

session_id = ""
thread_id = ""
action = "fresh"
stale_after_hours = 24
stale = False

if lane_state_path.exists():
    try:
        payload = json.loads(lane_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
else:
    payload = {}

record = payload.get(lane_name, {}) if isinstance(payload, dict) else {}
if isinstance(record, dict):
    stale_after_hours = int(record.get("stale_after_hours", stale_after_hours) or stale_after_hours)
    updated_at = record.get("updated_at_utc")
    if updated_at:
        try:
            parsed = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
            stale = (now - parsed).total_seconds() > stale_after_hours * 3600
        except ValueError:
            stale = False
    if dispatch_mode == "persistent" and not stale:
        session_id = str(record.get("session_id", "") or "")
        thread_id = str(record.get("thread_id", "") or "")
    if dispatch_mode == "persistent":
        if session_id:
            action = "resumed"
        elif updated_at and stale:
            action = "reset"
        else:
            action = "initialized"

print(session_id)
print(thread_id)
print(action)
print(stale_after_hours)
PY
)

CURRENT_SESSION_ID="${SESSION_META[0]}"
CURRENT_THREAD_ID="${SESSION_META[1]}"
SESSION_ACTION="${SESSION_META[2]}"
STALE_AFTER_HOURS="${SESSION_META[3]}"

PROMPT_TEXT="$(cat "${TMP_PROMPT}")"
CMD=()
LAST_MESSAGE="${RECEIPTS_DIR}/codex_${EVENT_ID}.last_message.md"

if [[ "${DISPATCH_MODE}" == "persistent" && -n "${CURRENT_SESSION_ID}" && ${USE_EXEC_RESUME} -eq 1 ]]; then
  CMD=("${CODEX_BIN}" "exec" "resume" "${CURRENT_SESSION_ID}" "--json" "-p" "${CODEX_PROFILE}" "--output-last-message" "${LAST_MESSAGE}" "${MODE_FLAGS[@]}" "${PROMPT_TEXT}")
elif [[ ${USE_EXEC} -eq 1 ]]; then
  CMD=("${CODEX_BIN}" "exec" "--json" "-C" "${TARGET_REPO_ROOT}" "-p" "${CODEX_PROFILE}" "--output-last-message" "${LAST_MESSAGE}" "${MODE_FLAGS[@]}" "${PROMPT_TEXT}")
else
  # Best-effort fallback for builds that expose direct prompt + quiet mode.
  CMD=("${CODEX_BIN}" "-C" "${TARGET_REPO_ROOT}" "${MODE_FLAGS[@]}" "-q" "${PROMPT_TEXT}")
fi

LOG_JSONL="${RECEIPTS_DIR}/codex_${EVENT_ID}.jsonl"
STDOUT_LOG="${RECEIPTS_DIR}/codex_${EVENT_ID}.stdout.log"
STDERR_LOG="${RECEIPTS_DIR}/codex_${EVENT_ID}.stderr.log"

{
  echo "# Codex dispatch receipt"
  echo
  echo "- event_id: ${EVENT_ID}"
  echo "- event_type: ${EVENT_TYPE}"
  echo "- mode: ${MODE}"
  echo "- lane_name: ${LANE_NAME}"
  echo "- dispatch_mode: ${DISPATCH_MODE}"
  echo "- codex_profile: ${CODEX_PROFILE}"
  echo "- template: ${TEMPLATE}"
  echo "- prompt_file: ${TMP_PROMPT}"
  echo "- codex_bin: ${CODEX_BIN}"
  echo "- used_exec: ${USE_EXEC}"
  echo "- used_exec_resume: ${USE_EXEC_RESUME}"
  echo "- repo_root: ${TARGET_REPO_ROOT}"
  echo "- lane_state_path: ${LANE_STATE_PATH}"
  echo "- session_action: ${SESSION_ACTION}"
  if [[ -n "${CURRENT_SESSION_ID}" ]]; then
    echo "- session_id: ${CURRENT_SESSION_ID}"
  fi
  if [[ -n "${CURRENT_THREAD_ID}" ]]; then
    echo "- thread_id: ${CURRENT_THREAD_ID}"
  fi
  echo "- stale_after_hours: ${STALE_AFTER_HOURS}"
  echo "- last_message: ${LAST_MESSAGE}"
  echo "- dry_run: ${DRY_RUN}"
  echo
  echo "## Command"
  printf -- '- %q ' "${CMD[@]}"
  echo
  echo
  echo "## Logs"
  echo "- stdout: ${STDOUT_LOG}"
  echo "- stderr: ${STDERR_LOG}"
  echo "- jsonl: ${LOG_JSONL}"
} > "${RECEIPT_PATH}"

if [[ ${DRY_RUN} -eq 1 ]]; then
  echo "[dry-run] would run:" | tee -a "${STDOUT_LOG}"
  printf '%q ' "${CMD[@]}" | tee -a "${STDOUT_LOG}"
  echo | tee -a "${STDOUT_LOG}"
  cp "${TMP_PROMPT}" "${RECEIPTS_DIR}/prompt_${EVENT_ID}.md"
  rm -f "${TMP_PROMPT}"
  exit 0
fi

# Preserve the prompt that was used.
cp "${TMP_PROMPT}" "${RECEIPTS_DIR}/prompt_${EVENT_ID}.md"

# Execute Codex with JSON output when exec is available.
set +e
pushd "${TARGET_REPO_ROOT}" >/dev/null
if [[ ${USE_EXEC} -eq 1 ]]; then
  "${CMD[@]}" > >(tee "${STDOUT_LOG}" "${LOG_JSONL}") 2> >(tee "${STDERR_LOG}" >&2)
else
  "${CMD[@]}" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" >&2)
fi
RC=$?
popd >/dev/null
set -e

NEW_SESSION_ID=""
NEW_THREAD_ID=""
if [[ ${USE_EXEC} -eq 1 && -f "${LOG_JSONL}" ]]; then
  readarray -t PARSED_IDS < <(python3 - "$LOG_JSONL" <<'PY'
import json, sys
from pathlib import Path

def visit(node, found):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "session_id" and isinstance(value, str) and value and not found["session_id"]:
                found["session_id"] = value
            elif key == "thread_id" and isinstance(value, str) and value and not found["thread_id"]:
                found["thread_id"] = value
            else:
                visit(value, found)
    elif isinstance(node, list):
        for item in node:
            visit(item, found)

found = {"session_id": "", "thread_id": ""}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        continue
    visit(payload, found)
print(found["session_id"])
print(found["thread_id"])
PY
)
  NEW_SESSION_ID="${PARSED_IDS[0]}"
  NEW_THREAD_ID="${PARSED_IDS[1]}"
fi

if [[ -z "${CURRENT_SESSION_ID}" && -n "${NEW_SESSION_ID}" ]]; then
  CURRENT_SESSION_ID="${NEW_SESSION_ID}"
fi
if [[ -z "${CURRENT_THREAD_ID}" && -n "${NEW_THREAD_ID}" ]]; then
  CURRENT_THREAD_ID="${NEW_THREAD_ID}"
fi

if [[ "${DISPATCH_MODE}" == "persistent" ]]; then
  python3 - "$LANE_STATE_PATH" "$LANE_NAME" "$CODEX_PROFILE" "$CURRENT_SESSION_ID" "$CURRENT_THREAD_ID" "$EVENT_ID" "$RECEIPT_PATH" "$STALE_AFTER_HOURS" "$SESSION_ACTION" <<'PY'
import json, sys
from datetime import datetime, timezone
from pathlib import Path

lane_state_path = Path(sys.argv[1])
lane_name = sys.argv[2]
profile = sys.argv[3]
session_id = sys.argv[4]
thread_id = sys.argv[5]
event_id = sys.argv[6]
receipt_path = sys.argv[7]
stale_after_hours = int(sys.argv[8] or "24")
session_action = sys.argv[9]

payload = {}
if lane_state_path.exists():
    try:
        payload = json.loads(lane_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = {}
if not isinstance(payload, dict):
    payload = {}

record = payload.get(lane_name, {}) if isinstance(payload.get(lane_name, {}), dict) else {}
record.update(
    {
        "lane_name": lane_name,
        "mode": "persistent",
        "profile": profile,
        "session_id": session_id,
        "thread_id": thread_id,
        "last_event_id": event_id,
        "last_receipt_path": receipt_path,
        "updated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "stale_after_hours": stale_after_hours,
    }
)
if session_action == "reset":
    record["reset_reason"] = "stale_session"
elif "reset_reason" in record:
    record.pop("reset_reason")
payload[lane_name] = record
lane_state_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
fi

echo >> "${RECEIPT_PATH}"
echo "## Exit" >> "${RECEIPT_PATH}"
echo "- code: ${RC}" >> "${RECEIPT_PATH}"
if [[ -n "${CURRENT_SESSION_ID}" ]]; then
  echo "- session_id: ${CURRENT_SESSION_ID}" >> "${RECEIPT_PATH}"
fi
if [[ -n "${CURRENT_THREAD_ID}" ]]; then
  echo "- thread_id: ${CURRENT_THREAD_ID}" >> "${RECEIPT_PATH}"
fi

rm -f "${TMP_PROMPT}"
exit "${RC}"
