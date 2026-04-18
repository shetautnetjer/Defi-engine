#!/usr/bin/env python3
import argparse, json, pathlib, sys, uuid
from datetime import datetime, timezone

def main():
    ap = argparse.ArgumentParser(description="Append an automation event to a JSONL queue.")
    ap.add_argument("--queue", required=True)
    ap.add_argument("--event-type", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--severity", default="medium", choices=["low", "medium", "high"])
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--notes", default="")
    ap.add_argument("--context-file", action="append", default=[])
    ap.add_argument("--qmd-report", action="append", default=[])
    ap.add_argument("--sql-ref", action="append", default=[])
    ap.add_argument("--log-file", action="append", default=[])
    args = ap.parse_args()

    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": args.event_type,
        "severity": args.severity,
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "repo_root": args.repo_root,
        "summary": args.summary,
        "notes": args.notes,
        "context_files": args.context_file,
        "qmd_reports": args.qmd_report,
        "sql_refs": args.sql_ref,
        "log_files": args.log_file,
    }
    q = pathlib.Path(args.queue)
    q.parent.mkdir(parents=True, exist_ok=True)
    with q.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event, indent=2))

if __name__ == "__main__":
    main()
