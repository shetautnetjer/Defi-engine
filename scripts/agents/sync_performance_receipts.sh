#!/usr/bin/env bash

set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=/dev/null
source "$script_dir/common.sh"

usage() {
  cat <<'EOF'
Usage: sync_performance_receipts.sh [--repo PATH]

Derive governed performance receipts from advisory realized-feedback metrics.
EOF
}

repo="${PWD}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      repo="${2:?--repo requires a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'sync_performance_receipts: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(defi_swarm_repo_root "$repo")"
defi_swarm_bootstrap_runtime_dirs "$repo_root"
receipts_dir="$(defi_swarm_performance_receipts_dir "$repo_root")"

python - "$repo_root" "$receipts_dir" <<'PY'
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(sys.argv[1])
receipts_dir = Path(sys.argv[2])
sys.path.insert(0, str(repo_root / "src"))

from d5_trading_engine.config.settings import get_settings  # noqa: E402

settings = get_settings()
db_path = settings.db_path
if not db_path.exists():
    raise SystemExit(0)

query = """
SELECT experiment_run_id, MAX(recorded_at) AS recorded_at
FROM experiment_metric
WHERE metric_name = 'realized_feedback_candidate_fills'
GROUP BY experiment_run_id
ORDER BY recorded_at DESC
LIMIT 1
"""

with sqlite3.connect(db_path) as conn:
    row = conn.execute(query).fetchone()
    if row is None:
        raise SystemExit(0)
    experiment_run_id, recorded_at = row
    metrics_rows = conn.execute(
        """
        SELECT metric_name, metric_value, recorded_at
        FROM experiment_metric
        WHERE experiment_run_id = ?
          AND metric_name LIKE 'realized_feedback_%'
        ORDER BY metric_name
        """,
        (experiment_run_id,),
    ).fetchall()

if not metrics_rows:
    raise SystemExit(0)

metrics = {name: float(value or 0.0) for name, value, _ in metrics_rows}
recorded_at = str(recorded_at or "")
safe_recorded_at = recorded_at.replace("-", "").replace(":", "").replace(" ", "T")
safe_recorded_at = safe_recorded_at.replace(".000000+00:00", "Z").replace("+00:00", "Z")
receipt_id = f"{safe_recorded_at}__{experiment_run_id}__performance"
output_path = receipts_dir / f"{receipt_id}.json"
if output_path.exists():
    raise SystemExit(0)

candidate_fills = metrics.get("realized_feedback_candidate_fills", 0.0)
matches = metrics.get("realized_feedback_matches", 0.0)
skipped = metrics.get("realized_feedback_skipped", 0.0)
missing_reports = metrics.get("realized_feedback_missing_reports", 0.0)
no_shadow_row = metrics.get("realized_feedback_no_shadow_row", 0.0)
match_ratio = (matches / candidate_fills) if candidate_fills else 0.0

recommendation = "no_action"
trigger_class = "performance_ok"
reasons: list[str] = []
if missing_reports > 0:
    recommendation = "review_doc_truth"
    trigger_class = "missing_reports"
    reasons.append("realized feedback found paper outcomes without the required reporting context")
elif no_shadow_row > 0 or skipped > 0:
    recommendation = "rerun_finder"
    trigger_class = "comparison_gap"
    reasons.append("realized feedback found unmatched or skipped paper outcomes that need design review")
elif candidate_fills > 0 and match_ratio < 0.5:
    recommendation = "rerun_finder"
    trigger_class = "weak_match_ratio"
    reasons.append("realized feedback match ratio fell below the conservative 0.50 monitoring threshold")

doc = {
    "receipt_id": receipt_id,
    "source": "experiment_realized_feedback_v1",
    "experiment_run_id": experiment_run_id,
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "recorded_at": recorded_at,
    "metrics": metrics,
    "summary": {
        "candidate_fills": candidate_fills,
        "matches": matches,
        "skipped": skipped,
        "missing_reports": missing_reports,
        "no_shadow_row": no_shadow_row,
        "match_ratio": match_ratio,
    },
    "trigger_class": trigger_class,
    "recommendation": recommendation,
    "reasons": reasons,
    "governance_note": (
        "This receipt is derived from advisory realized-feedback metrics and may only trigger "
        "finder or writer review. It does not promote backlog truth by itself."
    ),
}
output_path.write_text(json.dumps(doc, indent=2) + "\n")
print(str(output_path))
PY
