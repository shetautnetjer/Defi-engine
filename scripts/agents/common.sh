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

defi_swarm_bootstrap_runtime_dirs() {
  local repo_root="${1:?repo root required}"
  mkdir -p \
    "$repo_root/.ai/dropbox/research" \
    "$repo_root/.ai/dropbox/build" \
    "$repo_root/.ai/dropbox/architecture" \
    "$repo_root/.ai/dropbox/state"
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
