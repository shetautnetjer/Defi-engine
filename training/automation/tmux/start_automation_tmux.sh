#!/usr/bin/env bash
set -euo pipefail
SESSION_NAME="${SESSION_NAME:-d5-automation}"
ROOT="${ROOT:-$(pwd)}"

tmux has-session -t "${SESSION_NAME}" 2>/dev/null && {
  echo "tmux session ${SESSION_NAME} already exists"
  exit 0
}

tmux new-session -d -s "${SESSION_NAME}" -n engine "cd ${ROOT} && echo 'Start your engine here'"
tmux split-window -h -t "${SESSION_NAME}:0" "cd ${ROOT} && python automation/bin/codex_event_watcher.py --queue automation/state/events.jsonl --rules automation/config/automation_rules.json"
tmux split-window -v -t "${SESSION_NAME}:0.0" "cd ${ROOT} && tail -F automation/logs/latest.log 2>/dev/null || true"
tmux split-window -v -t "${SESSION_NAME}:0.1" "cd ${ROOT} && bash"
tmux select-layout -t "${SESSION_NAME}:0" tiled
tmux attach -t "${SESSION_NAME}"
