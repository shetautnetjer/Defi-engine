#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: update_story_state.sh --repo PATH --story-id ID --state ready|active|recovery|blocked_external|deferred|done|escalated
  [--receipt-id ID] [--recovery-round N]

Update a story state in prd.json. Story activation is owned by sync_swarm_state.sh.
EOF
}

repo="${PWD}"
story_id=""
state=""
receipt_id=""
recovery_round=""

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
    --state)
      state="${2:?--state requires a value}"
      shift 2
      ;;
    --receipt-id)
      receipt_id="${2:?--receipt-id requires a value}"
      shift 2
      ;;
    --recovery-round)
      recovery_round="${2:?--recovery-round requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'update_story_state: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
story_id="${story_id:-$(defi_swarm_active_story "$repo_root")}"

case "$state" in
  ready|active|recovery|blocked_external|deferred|done|escalated) ;;
  *)
    printf 'update_story_state: invalid state %s\n' "$state" >&2
    exit 2
    ;;
esac

if [[ -z "$story_id" || "$story_id" == "null" ]]; then
  printf 'update_story_state: no story id available\n' >&2
  exit 2
fi

python - "$repo_root/prd.json" "$story_id" "$state" "$receipt_id" "$recovery_round" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

prd_path = Path(sys.argv[1])
story_id = sys.argv[2]
new_state = sys.argv[3]
receipt_id = sys.argv[4]
recovery_round_arg = sys.argv[5]

doc = json.loads(prd_path.read_text())
stories = doc["userStories"]
target = next((story for story in stories if story["id"] == story_id), None)
if target is None:
    raise SystemExit(f"story not found: {story_id}")

target["state"] = new_state
target["passes"] = new_state == "done"
if recovery_round_arg:
    target["recovery_round"] = int(recovery_round_arg)
elif "recovery_round" not in target:
    target["recovery_round"] = 0
if "origin" not in target:
    target["origin"] = "seeded"
if "promoted_by" not in target:
    target["promoted_by"] = ""
if "stage" not in target:
    target["stage"] = "current_truth_consolidation"
if "ownerLayer" not in target:
    target["ownerLayer"] = "writer_integrator"
if "derivedFrom" not in target:
    target["derivedFrom"] = []
if "whyNow" not in target:
    target["whyNow"] = "Maintain bounded progress toward the north-star mission."
if "mustNotWiden" not in target:
    target["mustNotWiden"] = "Do not widen beyond the current bounded capability stage."
if "northStarLink" not in target:
    target["northStarLink"] = "docs/issues/governed_product_descent_capability_ladder.md"
if receipt_id:
    target["notes"] = (target.get("notes", "") + ("\n" if target.get("notes") else "") + f"last_receipt={receipt_id}").strip()

eligible = {"ready", "active", "recovery"}
if new_state == "done":
    target["recovery_round"] = 0
elif new_state == "recovery" and not recovery_round_arg:
    target["recovery_round"] = int(target.get("recovery_round", 0)) + 1

if new_state in eligible:
    doc["activeStoryId"] = story_id

prd_path.write_text(json.dumps(doc, indent=2) + "\n")
print(doc.get("activeStoryId", ""))
PY

"$script_dir/sync_swarm_state.sh" --repo "$repo_root" >/dev/null
