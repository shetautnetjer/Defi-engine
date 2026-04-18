#!/usr/bin/env python3
import argparse, json, pathlib, string, sys

def bullets(values):
    if not values:
        return "- (none)"
    return "\n".join(f"- {v}" for v in values)

def load_event(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    ap = argparse.ArgumentParser(description="Render a prompt template from an event JSON file.")
    ap.add_argument("--event-file", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--receipt-path", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    event = load_event(args.event_file)
    template_text = pathlib.Path(args.template).read_text(encoding="utf-8")
    values = {
        "EVENT_ID": event.get("event_id", ""),
        "EVENT_TYPE": event.get("event_type", ""),
        "SUMMARY": event.get("summary", ""),
        "REPO_ROOT": event.get("repo_root", "."),
        "NOTES": event.get("notes", ""),
        "RECEIPT_PATH": args.receipt_path,
        "QMD_REPORTS_BULLETS": bullets(event.get("qmd_reports", [])),
        "SQL_REFS_BULLETS": bullets(event.get("sql_refs", [])),
        "CONTEXT_FILES_BULLETS": bullets(event.get("context_files", [])),
        "LOG_FILES_BULLETS": bullets(event.get("log_files", [])),
    }
    out = string.Template(template_text).safe_substitute(values)
    pathlib.Path(args.output).write_text(out, encoding="utf-8")

if __name__ == "__main__":
    main()
