#!/usr/bin/env bash
set -euo pipefail

EVENT_FILE=""
RULES_FILE=""
RECEIPTS_DIR=""
DRY_RUN=0

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
print(cfg.get('template', 'automation/prompts/generic_review.md.tmpl'))
print(str(receipt))
print(event.get('event_id', 'unknown'))
print(event.get('event_type', 'unknown'))
PY
)

MODE="${META[0]}"
TEMPLATE="${META[1]}"
RECEIPT_PATH="${META[2]}"
EVENT_ID="${META[3]}"
EVENT_TYPE="${META[4]}"

TMP_PROMPT="$(mktemp)"
python3 automation/bin/render_prompt.py \
  --event-file "${EVENT_FILE}" \
  --template "${TEMPLATE}" \
  --receipt-path "${RECEIPT_PATH}" \
  --output "${TMP_PROMPT}"

if [[ "${MODE}" == "suggest" ]]; then
  MODE_FLAGS=()
elif [[ "${MODE}" == "auto-edit" ]]; then
  MODE_FLAGS=(--auto-edit)
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

PROMPT_TEXT="$(cat "${TMP_PROMPT}")"
CMD=()

if [[ ${USE_EXEC} -eq 1 ]]; then
  CMD=("${CODEX_BIN}" "exec" "${MODE_FLAGS[@]}" "${PROMPT_TEXT}")
else
  # Best-effort fallback for builds that expose direct prompt + quiet mode.
  CMD=("${CODEX_BIN}" "${MODE_FLAGS[@]}" "-q" "${PROMPT_TEXT}")
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
  echo "- template: ${TEMPLATE}"
  echo "- prompt_file: ${TMP_PROMPT}"
  echo "- codex_bin: ${CODEX_BIN}"
  echo "- used_exec: ${USE_EXEC}"
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

# Execute Codex; if exec supports JSON, callers can point CODEX_BIN to a wrapper that adds extra flags.
set +e
"${CMD[@]}" > >(tee "${STDOUT_LOG}") 2> >(tee "${STDERR_LOG}" >&2)
RC=$?
set -e

echo >> "${RECEIPT_PATH}"
echo "## Exit" >> "${RECEIPT_PATH}"
echo "- code: ${RC}" >> "${RECEIPT_PATH}"

rm -f "${TMP_PROMPT}"
exit "${RC}"
