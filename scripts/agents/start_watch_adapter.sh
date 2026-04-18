#!/usr/bin/env bash
set -euo pipefail

repo_root=""
interval="60"
dry_run="false"
audit_ai="false"
sandbox_evals="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo_root="${2:?--repo requires a path}"
      shift 2
      ;;
    --interval)
      interval="${2:?--interval requires a value}"
      shift 2
      ;;
    --dry-run)
      dry_run="true"
      shift
      ;;
    --audit-ai)
      audit_ai="true"
      shift
      ;;
    --sandbox-evals)
      sandbox_evals="true"
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$repo_root" ]]; then
  repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
fi

cd "$repo_root"

cmd=(python3 scripts/agents/codex_watch_adapter.py --repo "$repo_root" --loop --interval "$interval")
if [[ "$dry_run" == "true" ]]; then
  cmd+=(--dry-run)
fi
if [[ "$audit_ai" == "true" ]]; then
  cmd+=(--audit-ai)
fi
if [[ "$sandbox_evals" == "true" ]]; then
  cmd+=(--sandbox-evals)
fi

exec "${cmd[@]}"
