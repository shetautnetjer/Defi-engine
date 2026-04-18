#!/usr/bin/env bash
set -euo pipefail

repo_root=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo_root="${2:?--repo requires a path}"
      shift 2
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
exec python3 scripts/agents/codex_watch_adapter.py --repo "$repo_root" --status
