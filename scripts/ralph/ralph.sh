#!/usr/bin/env bash
# Ralph - repo-local writer-integrator loop runner
# Usage: ./scripts/ralph/ralph.sh [--tool codex|amp|claude] [--until-complete] [max_iterations]

set -euo pipefail

TOOL="codex"
MAX_ITERATIONS=10
UNTIL_COMPLETE="false"
SAFETY_LIMIT="${RALPH_SAFETY_LIMIT:-100}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)
      TOOL="${2:?--tool requires a value}"
      shift 2
      ;;
    --tool=*)
      TOOL="${1#*=}"
      shift
      ;;
    --until-complete)
      UNTIL_COMPLETE="true"
      shift
      ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
      fi
      shift
      ;;
  esac
done

if [[ ! "$TOOL" =~ ^(codex|amp|claude)$ ]]; then
  printf 'Error: Invalid tool %s. Must be codex, amp, or claude.\n' "$TOOL" >&2
  exit 1
fi

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(git -C "$SCRIPT_DIR/../.." rev-parse --show-toplevel 2>/dev/null || (cd "$SCRIPT_DIR/../.." && pwd -P))"
PRD_FILE="$REPO_ROOT/prd.json"
PROGRESS_FILE="$REPO_ROOT/progress.txt"
ARCHIVE_DIR="$REPO_ROOT/archive"
LAST_BRANCH_FILE="$SCRIPT_DIR/.last-branch"
RUNS_DIR="$SCRIPT_DIR/runs"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'ralph: required command not found: %s\n' "$1" >&2
    exit 127
  }
}

init_progress_file() {
  if [[ ! -f "$PROGRESS_FILE" ]]; then
    {
      printf '## Codebase Patterns\n'
      printf '\n'
      printf '# Ralph Progress Log\n'
      printf 'Started: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      printf '%s\n' '---'
    } > "$PROGRESS_FILE"
  fi
}

archive_previous_run_if_needed() {
  if [[ -f "$PRD_FILE" && -f "$LAST_BRANCH_FILE" ]]; then
    local current_branch=""
    local last_branch=""
    current_branch="$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || true)"
    last_branch="$(cat "$LAST_BRANCH_FILE" 2>/dev/null || true)"
    if [[ -n "$current_branch" && -n "$last_branch" && "$current_branch" != "$last_branch" ]]; then
      local date_part
      local folder_name
      local archive_folder
      date_part="$(date +%Y-%m-%d)"
      folder_name="$(echo "$last_branch" | sed 's|^ralph/||')"
      archive_folder="$ARCHIVE_DIR/$date_part-$folder_name"
      mkdir -p "$archive_folder"
      [[ -f "$PRD_FILE" ]] && cp "$PRD_FILE" "$archive_folder/"
      [[ -f "$PROGRESS_FILE" ]] && cp "$PROGRESS_FILE" "$archive_folder/"
      {
        printf '## Codebase Patterns\n'
        printf '\n'
        printf '# Ralph Progress Log\n'
        printf 'Started: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        printf '%s\n' '---'
      } > "$PROGRESS_FILE"
    fi
  fi
}

track_current_branch() {
  if [[ -f "$PRD_FILE" ]]; then
    local current_branch=""
    current_branch="$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || true)"
    if [[ -n "$current_branch" ]]; then
      printf '%s\n' "$current_branch" > "$LAST_BRANCH_FILE"
    fi
  fi
}

prompt_file_for_tool() {
  case "$1" in
    codex) printf '%s/CODEX.md\n' "$SCRIPT_DIR" ;;
    amp) printf '%s/prompt.md\n' "$SCRIPT_DIR" ;;
    claude) printf '%s/CLAUDE.md\n' "$SCRIPT_DIR" ;;
  esac
}

run_iteration() {
  local iteration="$1"
  local prompt_file="$2"
  local run_dir="$RUNS_DIR/$(date -u +%Y%m%dT%H%M%SZ)-iter-$iteration"
  mkdir -p "$run_dir"
  printf 'Run artifacts: %s\n' "$run_dir"

  local exit_code=0
  set +e
  case "$TOOL" in
    codex)
      require_cmd codex
      codex exec -C "$REPO_ROOT" --json -o "$run_dir/last-message.txt" - < "$prompt_file" \
        > >(tee "$run_dir/stdout.jsonl") \
        2> >(tee "$run_dir/stderr.log" >&2)
      exit_code=$?
      ;;
    amp)
      require_cmd amp
      amp --dangerously-allow-all < "$prompt_file" \
        > >(tee "$run_dir/stdout.log") \
        2> >(tee "$run_dir/stderr.log" >&2)
      exit_code=$?
      ;;
    claude)
      require_cmd claude
      claude --dangerously-skip-permissions --print < "$prompt_file" \
        > >(tee "$run_dir/stdout.log") \
        2> >(tee "$run_dir/stderr.log" >&2)
      exit_code=$?
      ;;
  esac
  set -e

  printf '%s\n' "$exit_code" > "$run_dir/exit-code.txt"

  if [[ -f "$run_dir/last-message.txt" ]] && grep -q '<promise>COMPLETE</promise>' "$run_dir/last-message.txt"; then
    return 10
  fi
  if [[ -f "$run_dir/stdout.jsonl" ]] && grep -q '<promise>COMPLETE</promise>' "$run_dir/stdout.jsonl"; then
    return 10
  fi
  if [[ -f "$run_dir/stdout.log" ]] && grep -q '<promise>COMPLETE</promise>' "$run_dir/stdout.log"; then
    return 10
  fi
  return 0
}

require_cmd jq
mkdir -p "$RUNS_DIR"
archive_previous_run_if_needed
track_current_branch
init_progress_file

if [[ "$UNTIL_COMPLETE" == "true" ]]; then
  printf 'Starting Ralph writer-integrator loop - Tool: %s - Until complete (safety limit: %s)\n' "$TOOL" "$SAFETY_LIMIT"
else
  printf 'Starting Ralph writer-integrator loop - Tool: %s - Max iterations: %s\n' "$TOOL" "$MAX_ITERATIONS"
fi

PROMPT_FILE="$(prompt_file_for_tool "$TOOL")"
if [[ ! -f "$PROMPT_FILE" ]]; then
  printf 'ralph: prompt file not found: %s\n' "$PROMPT_FILE" >&2
  exit 1
fi

iteration=1
while :; do
  if [[ "$UNTIL_COMPLETE" != "true" && "$iteration" -gt "$MAX_ITERATIONS" ]]; then
    break
  fi
  if [[ "$UNTIL_COMPLETE" == "true" && "$iteration" -gt "$SAFETY_LIMIT" ]]; then
    printf '\nRalph hit the safety limit (%s) without completing all tasks.\n' "$SAFETY_LIMIT"
    printf 'Check %s for status.\n' "$PROGRESS_FILE"
    exit 1
  fi

  printf '\n===============================================================\n'
  if [[ "$UNTIL_COMPLETE" == "true" ]]; then
    printf '  Ralph Iteration %s of until-complete (%s)\n' "$iteration" "$TOOL"
  else
    printf '  Ralph Iteration %s of %s (%s)\n' "$iteration" "$MAX_ITERATIONS" "$TOOL"
  fi
  printf '===============================================================\n'

  if run_iteration "$iteration" "$PROMPT_FILE"; then
    printf 'Iteration %s complete. Continuing...\n' "$iteration"
    sleep 2
  else
    status=$?
    if [[ "$status" -eq 10 ]]; then
      printf '\nRalph completed all tasks!\n'
      if [[ "$UNTIL_COMPLETE" == "true" ]]; then
        printf 'Completed at iteration %s\n' "$iteration"
      else
        printf 'Completed at iteration %s of %s\n' "$iteration" "$MAX_ITERATIONS"
      fi
      exit 0
    fi
    exit "$status"
  fi
  iteration=$((iteration + 1))
done

printf '\nRalph reached max iterations (%s) without completing all tasks.\n' "$MAX_ITERATIONS"
printf 'Check %s for status.\n' "$PROGRESS_FILE"
exit 1
