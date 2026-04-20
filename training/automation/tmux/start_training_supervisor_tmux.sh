#!/usr/bin/env bash
set -euo pipefail

SESSION_NAME="${SESSION_NAME:-d5-training-supervisor}"
ROOT="${ROOT:-$(pwd)}"
REPO_ROOT="$(cd "${ROOT}" && pwd)"
LOG_DIR="${REPO_ROOT}/data/research/training/runtime"
ATTACH="${ATTACH:-auto}"

mkdir -p "${LOG_DIR}"
LOG_PATH="${LOG_DIR}/d5_training_supervisor_$(date -u +%Y%m%dT%H%M%SZ).log"

tmux has-session -t "${SESSION_NAME}" 2>/dev/null && {
  echo "tmux session ${SESSION_NAME} already exists"
  exit 0
}

tmux new-session -d -s "${SESSION_NAME}" -n supervisor \
  "cd ${REPO_ROOT} && python training/automation/bin/training_supervisor.py 2>&1 | tee -a ${LOG_PATH}"

if [[ "${ATTACH}" == "1" || "${ATTACH}" == "true" || ( "${ATTACH}" == "auto" && -t 1 ) ]]; then
  tmux attach -t "${SESSION_NAME}"
else
  echo "tmux session ${SESSION_NAME} started"
  echo "log: ${LOG_PATH}"
  echo "attach with: tmux attach -t ${SESSION_NAME}"
fi
