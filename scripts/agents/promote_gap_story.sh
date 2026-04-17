#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: promote_gap_story.sh --repo PATH [--source-story ID] --receipt-id ID --title TEXT --description TEXT --priority N \
  --acceptance TEXT [--acceptance TEXT ...] [--family PREFIX] [--make-active] \
  [--stage STAGE] [--owner-layer LAYER] [--derived-from VALUE ...] \
  [--why-now TEXT] [--must-not-widen TEXT] [--north-star-link TEXT]

Promote a newly discovered gap into prd.json as a ready story.
EOF
}

repo="${PWD}"
source_story=""
receipt_id=""
title=""
description=""
priority=""
family=""
make_active="false"
stage="current_truth_consolidation"
owner_layer="writer_integrator"
why_now=""
must_not_widen="Do not widen beyond the current bounded capability stage."
north_star_link="docs/issues/governed_product_descent_capability_ladder.md"
declare -a acceptance=()
declare -a derived_from=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    --source-story)
      source_story="${2:?--source-story requires a value}"
      shift 2
      ;;
    --receipt-id)
      receipt_id="${2:?--receipt-id requires a value}"
      shift 2
      ;;
    --title)
      title="${2:?--title requires a value}"
      shift 2
      ;;
    --description)
      description="${2:?--description requires a value}"
      shift 2
      ;;
    --priority)
      priority="${2:?--priority requires a value}"
      shift 2
      ;;
    --acceptance)
      acceptance+=("${2:?--acceptance requires a value}")
      shift 2
      ;;
    --family)
      family="${2:?--family requires a value}"
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
    --derived-from)
      derived_from+=("${2:?--derived-from requires a value}")
      shift 2
      ;;
    --why-now)
      why_now="${2:?--why-now requires a value}"
      shift 2
      ;;
    --must-not-widen)
      must_not_widen="${2:?--must-not-widen requires a value}"
      shift 2
      ;;
    --north-star-link)
      north_star_link="${2:?--north-star-link requires a value}"
      shift 2
      ;;
    --make-active)
      make_active="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'promote_gap_story: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
source_story="${source_story:-$(defi_swarm_active_story "$repo_root")}"

if [[ -z "$receipt_id" || -z "$title" || -z "$description" || -z "$priority" || ${#acceptance[@]} -eq 0 ]]; then
  printf 'promote_gap_story: receipt, title, description, priority, and at least one acceptance criterion are required\n' >&2
  exit 2
fi

family="${family:-${source_story%%-*}}"
why_now="${why_now:-Receipt-backed follow-on promoted by writer-integrator from accepted repo truth.}"
if [[ ${#derived_from[@]} -eq 0 ]]; then
  derived_from+=("$receipt_id")
fi

ACCEPTANCE_JSON="$(printf '%s\n' "${acceptance[@]}" | jq -R . | jq -s .)"
export ACCEPTANCE_JSON
DERIVED_FROM_JSON="$(printf '%s\n' "${derived_from[@]}" | jq -R . | jq -s .)"
export DERIVED_FROM_JSON

python - "$repo_root/prd.json" "$family" "$title" "$description" "$priority" "$receipt_id" "$make_active" "$stage" "$owner_layer" "$why_now" "$must_not_widen" "$north_star_link" <<'PY'
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

prd_path = Path(sys.argv[1])
family = sys.argv[2]
title = sys.argv[3]
description = sys.argv[4]
priority = int(sys.argv[5])
receipt_id = sys.argv[6]
make_active = sys.argv[7] == "true"
stage = sys.argv[8]
owner_layer = sys.argv[9]
why_now = sys.argv[10]
must_not_widen = sys.argv[11]
north_star_link = sys.argv[12]
acceptance = json.loads(os.environ["ACCEPTANCE_JSON"])
derived_from = json.loads(os.environ["DERIVED_FROM_JSON"])

doc = json.loads(prd_path.read_text())
stories = doc["userStories"]

pattern = re.compile(rf"^{re.escape(family)}-(\d+)$")
numbers = []
for story in stories:
    match = pattern.match(story["id"])
    if match:
        numbers.append(int(match.group(1)))
next_number = (max(numbers) + 1) if numbers else 1
story_id = f"{family}-{next_number:03d}"

story = {
    "id": story_id,
    "title": title,
    "description": description,
    "acceptanceCriteria": acceptance,
    "priority": priority,
    "passes": False,
    "notes": "",
    "state": "ready",
    "recovery_round": 0,
    "origin": "promoted_gap",
    "promoted_by": receipt_id,
    "stage": stage,
    "ownerLayer": owner_layer,
    "derivedFrom": derived_from,
    "whyNow": why_now,
    "mustNotWiden": must_not_widen,
    "northStarLink": north_star_link,
}
stories.append(story)
stories.sort(key=lambda item: (item.get("priority", 9999), item["id"]))
if make_active:
    doc["activeStoryId"] = story_id
prd_path.write_text(json.dumps(doc, indent=2) + "\n")
print(story_id)
PY

"$script_dir/sync_swarm_state.sh" --repo "$repo_root" >/dev/null
