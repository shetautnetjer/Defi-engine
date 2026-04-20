#!/usr/bin/env bash
set -euo pipefail
SESSION_NAME="${SESSION_NAME:-d5-automation}"
ROOT="${ROOT:-$(pwd)}"
REPO_ROOT="$(cd "${ROOT}" && pwd)"
LOG_DIR="${REPO_ROOT}/training/automation/logs"
ATTACH="${ATTACH:-auto}"

mkdir -p "${LOG_DIR}"

tmux has-session -t "${SESSION_NAME}" 2>/dev/null && {
  echo "tmux session ${SESSION_NAME} already exists"
  exit 0
}

tmux new-session -d -s "${SESSION_NAME}" -n engine "cd ${REPO_ROOT} && bash"
tmux split-window -h -t "${SESSION_NAME}:0" "cd ${REPO_ROOT} && python training/automation/bin/codex_event_watcher.py 2>&1 | tee -a ${LOG_DIR}/watcher.log"
tmux split-window -v -t "${SESSION_NAME}:0.0" "cd ${REPO_ROOT} && tail -F ${LOG_DIR}/watcher.log 2>/dev/null || true"
tmux split-window -v -t "${SESSION_NAME}:0.1" "cd ${REPO_ROOT} && bash"
tmux select-layout -t "${SESSION_NAME}:0" tiled
if [[ "${ATTACH}" == "1" || "${ATTACH}" == "true" || ( "${ATTACH}" == "auto" && -t 1 ) ]]; then
  tmux attach -t "${SESSION_NAME}"
else
  echo "tmux session ${SESSION_NAME} started"
  echo "attach with: tmux attach -t ${SESSION_NAME}"
fi
