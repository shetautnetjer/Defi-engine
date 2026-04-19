#!/usr/bin/env python3
import argparse, json, pathlib, subprocess, sys, time, hashlib
from datetime import datetime, timezone

def load_state(path):
    if not path.exists():
        return {"offset": 0, "processed_ids": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"offset": 0, "processed_ids": []}

def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_lane_sessions(path):
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def save_status(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def next_events(queue_path, state):
    events = []
    if not queue_path.exists():
        return events
    with queue_path.open("r", encoding="utf-8") as f:
        f.seek(state.get("offset", 0))
        while True:
            pos = f.tell()
            line = f.readline()
            if not line:
                state["offset"] = pos
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            events.append(obj)
        state["offset"] = f.tell()
    return events

def event_file_from_obj(event, cache_dir):
    cache_dir.mkdir(parents=True, exist_ok=True)
    event_id = event.get("event_id") or hashlib.sha1(json.dumps(event, sort_keys=True).encode()).hexdigest()[:12]
    path = cache_dir / f"{event_id}.json"
    path.write_text(json.dumps(event, indent=2), encoding="utf-8")
    return path

def dispatch(dispatch_script, event_file, rules, receipts_dir, dry_run):
    cmd = [str(dispatch_script), "--event-file", str(event_file), "--rules", str(rules), "--receipts-dir", str(receipts_dir)]
    if dry_run:
        cmd.append("--dry-run")
    return subprocess.run(cmd, text=True, capture_output=True)

def main():
    ap = argparse.ArgumentParser(description="Watch an event queue and trigger Codex tasks.")
    ap.add_argument("--queue", default="automation/state/events.jsonl")
    ap.add_argument("--rules", default="automation/config/automation_rules.json")
    ap.add_argument("--state-file", default="automation/state/watcher_state.json")
    ap.add_argument("--status-file", default="automation/state/watcher_status.json")
    ap.add_argument("--cache-dir", default="automation/state/expanded_events")
    ap.add_argument("--receipts-dir", default="automation/receipts")
    ap.add_argument("--dispatch-script", default="automation/bin/codex_dispatch.sh")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    queue_path = pathlib.Path(args.queue)
    rules_path = pathlib.Path(args.rules)
    state_path = pathlib.Path(args.state_file)
    status_path = pathlib.Path(args.status_file)
    cache_dir = pathlib.Path(args.cache_dir)
    dispatch_script = pathlib.Path(args.dispatch_script)
    receipts_dir = pathlib.Path(args.receipts_dir)
    lane_state_path = queue_path.parent / "lane_sessions.json"

    state = load_state(state_path)
    last_event = None
    last_result = None

    while True:
        events = next_events(queue_path, state)
        processed = set(state.get("processed_ids", []))
        for event in events:
            event_id = event.get("event_id")
            if event_id and event_id in processed:
                continue
            event_file = event_file_from_obj(event, cache_dir)
            result = dispatch(dispatch_script, event_file, rules_path, receipts_dir, args.dry_run)
            sys.stdout.write(result.stdout)
            sys.stderr.write(result.stderr)
            last_event = event
            last_result = result
            if result.returncode == 0 and event_id:
                processed.add(event_id)

        state["processed_ids"] = sorted(list(processed))[-500:]
        save_state(state_path, state)
        lane_sessions = load_lane_sessions(lane_state_path)
        trader_lane = lane_sessions.get("trader", {}) if isinstance(lane_sessions.get("trader", {}), dict) else {}
        watcher_status = {
            "status": "once_complete" if args.once else ("dispatch_failed" if last_result and last_result.returncode != 0 else "idle"),
            "queue_path": str(queue_path),
            "rules_path": str(rules_path),
            "state_file": str(state_path),
            "receipts_dir": str(receipts_dir),
            "offset": state.get("offset", 0),
            "processed_count": len(state.get("processed_ids", [])),
            "updated_at_utc": utcnow_iso(),
        }
        if last_event:
            watcher_status["last_event_id"] = last_event.get("event_id", "")
            watcher_status["last_event_type"] = last_event.get("event_type", "")
        if last_result is not None:
            watcher_status["last_dispatch_ok"] = last_result.returncode == 0
            watcher_status["last_dispatch_returncode"] = last_result.returncode
        if trader_lane:
            watcher_status["trader_lane"] = {
                "session_id": trader_lane.get("session_id", ""),
                "thread_id": trader_lane.get("thread_id", ""),
                "profile": trader_lane.get("profile", ""),
                "last_event_id": trader_lane.get("last_event_id", ""),
                "updated_at_utc": trader_lane.get("updated_at_utc", ""),
            }
        save_status(status_path, watcher_status)

        if args.once:
            break
        time.sleep(args.interval)

if __name__ == "__main__":
    main()
