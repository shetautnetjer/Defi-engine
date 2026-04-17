#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: commit_accepted_story.sh [--repo PATH] [--receipt-id ID]

Create one governed commit for a new accepted receipt. Never pushes.
EOF
}

repo="${PWD}"
receipt_id=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    --receipt-id)
      receipt_id="${2:?--receipt-id requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'commit_accepted_story: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
state_path="$(defi_swarm_auto_commit_state_path "$repo_root")"

python - "$repo_root" "$state_path" "$receipt_id" <<'PY'
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
state_path = Path(sys.argv[2])
requested_receipt_id = sys.argv[3]

state = json.loads(state_path.read_text())
last_auto_commit_receipt_id = str(state.get("lastAutoCommitReceiptId") or "")
receipts_dir = repo_root / ".ai" / "dropbox" / "state" / "accepted_receipts"

receipt_path: Path | None = None
if requested_receipt_id:
    candidate = receipts_dir / f"{requested_receipt_id}.json"
    if candidate.exists():
        receipt_path = candidate
else:
    matches = sorted(receipts_dir.glob("*.json"))
    if matches:
        receipt_path = matches[-1]

if receipt_path is None:
    raise SystemExit(0)

receipt = json.loads(receipt_path.read_text())
receipt_id = str(receipt.get("receipt_id") or "")
story_id = str(receipt.get("story_id") or "")
decision = str(receipt.get("decision") or "")
if not receipt_id or receipt_id == last_auto_commit_receipt_id or decision != "accept":
    raise SystemExit(0)

stage_paths = [
    repo_root / "prd.json",
    repo_root / "progress.txt",
    repo_root / ".ai" / "dropbox" / "state" / "accepted_loops.md",
    repo_root / ".ai" / "dropbox" / "state" / "open_questions.md",
    repo_root / ".ai" / "dropbox" / "state" / "rejections.md",
    receipt_path,
]
for raw_path in receipt.get("candidate_artifacts", []):
    candidate = repo_root / str(raw_path)
    if candidate.exists():
        stage_paths.append(candidate)

tracked_paths = []
for path in stage_paths:
    if not path.exists():
        continue
    try:
        path.relative_to(repo_root)
    except ValueError:
        continue
    tracked_paths.append(path)

if not tracked_paths:
    raise SystemExit(0)

for path in tracked_paths:
    subprocess.run(["git", "add", "--", str(path.relative_to(repo_root))], cwd=repo_root, check=True)

diff_check = subprocess.run(
    ["git", "diff", "--cached", "--quiet"],
    cwd=repo_root,
    check=False,
)
if diff_check.returncode == 0:
    raise SystemExit(0)

summary = str(receipt.get("rationale") or "").strip().splitlines()[0]
if not summary:
    summary = "receipt-backed accepted slice"
message = f"story({story_id}): {receipt_id} {summary}"
subprocess.run(["git", "commit", "-m", message], cwd=repo_root, check=True)
commit_sha = (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo_root, text=True).strip()
)
state["lastAutoCommitReceiptId"] = receipt_id
state["lastCommitSha"] = commit_sha
state["updatedAt"] = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
state_path.write_text(json.dumps(state, indent=2) + "\n")
print(commit_sha)
PY
