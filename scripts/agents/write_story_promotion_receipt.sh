#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: write_story_promotion_receipt.sh --repo PATH [--story-id ID] --stage STAGE \
  --owner-layer LAYER --why-now TEXT --north-star-link TEXT --summary TEXT \
  [--docs-reviewed PATH ...] [--issue-doc PATH ...] [--gap-doc PATH ...] \
  [--story-created ID ...] [--story-updated ID ...] [--deferred TEXT ...] \
  [--proposal-source TEXT ...]

Write the latest writer promotion decision to .ai/dropbox/state/story_promotion_receipt.json.
EOF
}

repo="${PWD}"
story_id=""
stage=""
owner_layer=""
why_now=""
north_star_link=""
summary=""
declare -a docs_reviewed=()
declare -a issue_docs=()
declare -a gap_docs=()
declare -a stories_created=()
declare -a stories_updated=()
declare -a deferred_items=()
declare -a proposal_sources=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    --story-id)
      story_id="${2:?--story-id requires a value}"
      shift 2
      ;;
    --stage)
      stage="${2:?--stage requires a value}"
      shift 2
      ;;
    --owner-layer)
      owner_layer="${2:?--owner-layer requires a value}"
      shift 2
      ;;
    --why-now)
      why_now="${2:?--why-now requires a value}"
      shift 2
      ;;
    --north-star-link)
      north_star_link="${2:?--north-star-link requires a value}"
      shift 2
      ;;
    --summary)
      summary="${2:?--summary requires a value}"
      shift 2
      ;;
    --docs-reviewed)
      docs_reviewed+=("${2:?--docs-reviewed requires a value}")
      shift 2
      ;;
    --issue-doc)
      issue_docs+=("${2:?--issue-doc requires a value}")
      shift 2
      ;;
    --gap-doc)
      gap_docs+=("${2:?--gap-doc requires a value}")
      shift 2
      ;;
    --story-created)
      stories_created+=("${2:?--story-created requires a value}")
      shift 2
      ;;
    --story-updated)
      stories_updated+=("${2:?--story-updated requires a value}")
      shift 2
      ;;
    --deferred)
      deferred_items+=("${2:?--deferred requires a value}")
      shift 2
      ;;
    --proposal-source)
      proposal_sources+=("${2:?--proposal-source requires a value}")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'write_story_promotion_receipt: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
story_id="${story_id:-$(defi_swarm_active_story "$repo_root")}"

if [[ -z "$stage" || -z "$owner_layer" || -z "$why_now" || -z "$north_star_link" || -z "$summary" ]]; then
  printf 'write_story_promotion_receipt: --stage, --owner-layer, --why-now, --north-star-link, and --summary are required\n' >&2
  exit 2
fi

output_path="$(defi_swarm_story_promotion_receipt_path "$repo_root")"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
receipt_id="story_promotion::${story_id:-none}::${timestamp}"

python - "$output_path" "$receipt_id" "$story_id" "$stage" "$owner_layer" "$why_now" "$north_star_link" "$summary" "$timestamp" <<'PY' \
  "${docs_reviewed[@]}" -- "${issue_docs[@]}" -- "${gap_docs[@]}" -- "${stories_created[@]}" -- "${stories_updated[@]}" -- "${deferred_items[@]}" -- "${proposal_sources[@]}"
from __future__ import annotations

import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
receipt_id = sys.argv[2]
story_id = sys.argv[3]
stage = sys.argv[4]
owner_layer = sys.argv[5]
why_now = sys.argv[6]
north_star_link = sys.argv[7]
summary = sys.argv[8]
updated_at = sys.argv[9]

parts = sys.argv[10:]
groups: list[list[str]] = [[]]
for item in parts:
    if item == "--":
        groups.append([])
        continue
    groups[-1].append(item)

while len(groups) < 7:
    groups.append([])

doc = {
    "receipt_id": receipt_id,
    "story_id": story_id,
    "stage": stage,
    "owner_layer": owner_layer,
    "why_now": why_now,
    "north_star_link": north_star_link,
    "docs_reviewed": groups[0],
    "issue_docs_updated": groups[1],
    "gap_docs_updated": groups[2],
    "stories_created": groups[3],
    "stories_updated": groups[4],
    "deferred_items": groups[5],
    "proposal_sources": groups[6],
    "summary": summary,
    "updated_at": updated_at,
}
output_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
print(str(output_path))
PY
