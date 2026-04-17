#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: write_acceptance_receipt.sh --repo PATH [--story-id ID] --decision accept|reject|block|escalate \
  [--promotion-status pending|complete|not_applicable] [--lane writer-integrator] \
  [--upstream-artifact PATH ...] [--candidate-artifact PATH ...] [--check TEXT ...] \
  [--contradiction TEXT ...] [--risk TEXT ...] [--missing-capability TEXT ...] \
  [--promotion-target TEXT ...] [--derived-from-receipt ID ...] \
  [--owner-layer LAYER] [--stage STAGE] [--must-not-widen TEXT ...] \
  --rationale TEXT --next-action TEXT

Write one structured acceptance receipt JSON under .ai/dropbox/state/accepted_receipts/.
EOF
}

repo="${PWD}"
story_id=""
decision=""
promotion_status="not_applicable"
lane="writer-integrator"
rationale=""
next_action=""
declare -a upstream_artifacts=()
declare -a candidate_artifacts=()
declare -a checks_run=()
declare -a contradictions=()
declare -a risks=()
declare -a missing_capabilities=()
declare -a promotion_targets=()
declare -a must_not_widen=()
declare -a derived_from_receipts=()
owner_layer=""
stage=""

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
    --decision)
      decision="${2:?--decision requires a value}"
      shift 2
      ;;
    --promotion-status)
      promotion_status="${2:?--promotion-status requires a value}"
      shift 2
      ;;
    --lane)
      lane="${2:?--lane requires a value}"
      shift 2
      ;;
    --upstream-artifact)
      upstream_artifacts+=("${2:?--upstream-artifact requires a value}")
      shift 2
      ;;
    --candidate-artifact)
      candidate_artifacts+=("${2:?--candidate-artifact requires a value}")
      shift 2
      ;;
    --check)
      checks_run+=("${2:?--check requires a value}")
      shift 2
      ;;
    --contradiction)
      contradictions+=("${2:?--contradiction requires a value}")
      shift 2
      ;;
    --risk)
      risks+=("${2:?--risk requires a value}")
      shift 2
      ;;
    --missing-capability)
      missing_capabilities+=("${2:?--missing-capability requires a value}")
      shift 2
      ;;
    --promotion-target)
      promotion_targets+=("${2:?--promotion-target requires a value}")
      shift 2
      ;;
    --derived-from-receipt)
      derived_from_receipts+=("${2:?--derived-from-receipt requires a value}")
      shift 2
      ;;
    --owner-layer)
      owner_layer="${2:?--owner-layer requires a value}"
      shift 2
      ;;
    --stage)
      stage="${2:?--stage requires a value}"
      shift 2
      ;;
    --must-not-widen)
      must_not_widen+=("${2:?--must-not-widen requires a value}")
      shift 2
      ;;
    --rationale)
      rationale="${2:?--rationale requires a value}"
      shift 2
      ;;
    --next-action)
      next_action="${2:?--next-action requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'write_acceptance_receipt: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
story_id="${story_id:-$(defi_swarm_active_story "$repo_root")}"

if [[ -z "$story_id" || "$story_id" == "null" ]]; then
  printf 'write_acceptance_receipt: no story id available\n' >&2
  exit 2
fi

case "$decision" in
  accept|reject|block|escalate) ;;
  *)
    printf 'write_acceptance_receipt: invalid decision %s\n' "$decision" >&2
    exit 2
    ;;
esac

case "$promotion_status" in
  pending|complete|not_applicable) ;;
  *)
    printf 'write_acceptance_receipt: invalid promotion status %s\n' "$promotion_status" >&2
    exit 2
    ;;
esac

if [[ -z "$rationale" || -z "$next_action" ]]; then
  printf 'write_acceptance_receipt: --rationale and --next-action are required\n' >&2
  exit 2
fi

receipts_dir="$(defi_swarm_accepted_receipts_dir "$repo_root")"
timestamp="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
safe_timestamp="$(date -u +%Y-%m-%dT%H%M%SZ)"
receipt_id="${safe_timestamp}__${story_id}"
output_path="$receipts_dir/${receipt_id}.json"

python - "$output_path" "$receipt_id" "$story_id" "$decision" "$promotion_status" "$lane" "$timestamp" "$rationale" "$next_action" "$owner_layer" "$stage" <<'PY' \
  "${upstream_artifacts[@]}" -- "${candidate_artifacts[@]}" -- "${checks_run[@]}" -- "${contradictions[@]}" -- "${risks[@]}" -- "${missing_capabilities[@]}" -- "${promotion_targets[@]}" -- "${must_not_widen[@]}" -- "${derived_from_receipts[@]}"
from __future__ import annotations

import json
import sys
from pathlib import Path

output_path = Path(sys.argv[1])
receipt_id = sys.argv[2]
story_id = sys.argv[3]
decision = sys.argv[4]
promotion_status = sys.argv[5]
lane = sys.argv[6]
timestamp = sys.argv[7]
rationale = sys.argv[8]
next_action = sys.argv[9]
owner_layer = sys.argv[10]
stage = sys.argv[11]

parts = sys.argv[12:]

groups: list[list[str]] = [[]]
for item in parts:
    if item == "--":
        groups.append([])
        continue
    groups[-1].append(item)

while len(groups) < 9:
    groups.append([])

doc = {
    "receipt_id": receipt_id,
    "story_id": story_id,
    "decision": decision,
    "promotion_status": promotion_status,
    "lane": lane,
    "timestamp": timestamp,
    "upstream_artifacts_consumed": groups[0],
    "candidate_artifacts": groups[1],
    "checks_run": groups[2],
    "contradictions_found": groups[3],
    "unresolved_risks": groups[4],
    "missing_capabilities": groups[5],
    "promotion_targets": groups[6],
    "must_not_widen": groups[7],
    "derived_from_receipt_ids": groups[8],
    "owner_layer": owner_layer,
    "stage": stage,
    "rationale": rationale,
    "next_action": next_action,
}
output_path.write_text(json.dumps(doc, indent=2) + "\n")
print(str(output_path))
PY
