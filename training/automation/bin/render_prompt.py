#!/usr/bin/env python3
import argparse
import json
import pathlib
import string
import subprocess
import sys

def bullets(values):
    if not values:
        return "- (none)"
    return "\n".join(f"- {v}" for v in values)

def load_event(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def script_repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[3]


def resolve_training_context(event_file: pathlib.Path, repo_root: pathlib.Path) -> dict:
    helper = script_repo_root() / "training" / "bin" / "resolve_training_context.py"
    cmd = [
        sys.executable,
        str(helper),
        "--event-file",
        str(event_file),
        "--repo-root",
        str(repo_root),
    ]
    completed = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    return payload if isinstance(payload, dict) else {}

def main():
    ap = argparse.ArgumentParser(description="Render a prompt template from an event JSON file.")
    ap.add_argument("--event-file", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--receipt-path", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    event_file = pathlib.Path(args.event_file)
    event = load_event(event_file)
    repo_root = pathlib.Path(event.get("repo_root") or script_repo_root()).resolve()
    context = resolve_training_context(event_file, repo_root)
    template_text = pathlib.Path(args.template).read_text(encoding="utf-8")
    doc_paths = context.get("doc_paths", {})
    values = {
        "EVENT_ID": event.get("event_id", ""),
        "EVENT_TYPE": event.get("event_type", ""),
        "SUMMARY": event.get("summary", ""),
        "REPO_ROOT": str(repo_root),
        "NOTES": event.get("notes", ""),
        "RECEIPT_PATH": args.receipt_path,
        "QMD_REPORTS_BULLETS": bullets(event.get("qmd_reports", [])),
        "SQL_REFS_BULLETS": bullets(event.get("sql_refs", [])),
        "CONTEXT_FILES_BULLETS": bullets(event.get("context_files", [])),
        "LOG_FILES_BULLETS": bullets(event.get("log_files", [])),
        "ROOT_AGENTS_PATH": doc_paths.get("root_agents", "AGENTS.md"),
        "TRAINING_AGENTS_PATH": doc_paths.get("training_agents", "training/AGENTS.md"),
        "TRAINING_README_PATH": doc_paths.get("training_readme", "training/README.md"),
        "TRADING_HARNESS_PATH": doc_paths.get(
            "trading_harness",
            "training/trading_agent_harness.md",
        ),
        "TRAINING_PROGRAM_PATH": doc_paths.get("training_program", "training/program.md"),
        "TRAINING_RUBRIC_PATH": doc_paths.get(
            "training_rubric",
            "training/rubrics/training_regime_rubric.md",
        ),
        "TRAINING_DOC_READ_ORDER_BULLETS": bullets(
            context.get("training_doc_read_order", [])
        ),
        "ALLOWED_SURFACES_BULLETS": bullets(
            context.get("allowed_change_surfaces", [])
        ),
        "TARGET_SURFACE": context.get("target_surface", "one bounded training surface"),
        "KEEP_REVERT_SHADOW_RULE": context.get(
            "keep_revert_shadow_rule",
            "Keep the current accepted baseline unless a bounded candidate clearly improves evidence; otherwise revert or shadow.",
        ),
        "ACTIVE_PROFILE_REVISION_ID": context.get("active_profile_revision_id", ""),
        "ACTIVE_PROFILE_SUMMARY": context.get(
            "active_profile_summary",
            "no active profile summary available",
        ),
        "HISTORICAL_CACHE_SUMMARY": context.get(
            "historical_cache_summary",
            "historical cache status unavailable",
        ),
        "BASELINE_BULLETS": bullets(context.get("baseline_refs", [])),
        "RESOLVED_QMD_REPORTS_BULLETS": bullets(
            context.get("resolved_qmd_reports", [])
        ),
        "RESOLVED_SQL_REFS_BULLETS": bullets(
            context.get("resolved_sql_refs", [])
        ),
        "PRIMARY_QMD_PATH": context.get("primary_qmd_path", ""),
    }
    out = string.Template(template_text).safe_substitute(values)
    pathlib.Path(args.output).write_text(out, encoding="utf-8")

if __name__ == "__main__":
    main()
