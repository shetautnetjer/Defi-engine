#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


REQUIRED_DOCS = [
    "docs/issues/governed_product_descent_capability_ladder.md",
    "docs/gaps/backtest_truth_model_gap.md",
    "docs/gaps/label_program_and_regime_taxonomy_gap.md",
    "docs/gaps/strategy_registry_and_challenger_framework_gap.md",
    "docs/gaps/execution_intent_gap.md",
    "docs/gaps/instrument_expansion_readiness_gap.md",
    "docs/gaps/tmux_machine_law_and_packet_gap.md",
]

FORBIDDEN_SNIPPETS: dict[str, list[str]] = {
    "docs/prd/crypto_backtesting_mission.md": [
        "continuous capture ownership across the required lanes",
        "realized-feedback comparison between `research_loop/` and paper outcomes",
    ],
    "docs/runbooks/feature_condition_shadow_cycle.md": [
        "This runbook does not imply policy-owned trade eligibility",
        "This runbook does not imply a hard risk gate",
        "This runbook does not imply paper-session ownership",
        "This runbook does not imply paper fills / settlement receipts",
    ],
    "docs/math/regime_shadow_modeling_contracts.md": [
        "The repo does not yet imply policy-owned trade eligibility",
        "a hard risk gate",
        "paper fills or settlement truth",
    ],
    "docs/gaps/bootstrap_gap_register.md": [
        "still remain placeholder boundaries",
        "policy, risk, and settlement placeholders",
    ],
}

REQUIRED_SNIPPETS: dict[str, list[str]] = {
    "docs/project/current_runtime_truth.md": [
        "Stage 1",
        "current-truth consolidation",
        "execution intent",
    ],
    "docs/runbooks/ralph_tmux_swarm.md": [
        "docs_truth_receipt.json",
        "docs_sync_status.json",
        "repo-wide docs-truth scan",
    ],
    ".ai/agents/writer_integrator.md": [
        "check_doc_truth.py",
        "docs_truth_receipt.json",
        "docs_sync_status.json",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate repo-wide docs truth surfaces.")
    parser.add_argument("--repo", default=".", help="Repo root")
    parser.add_argument("--story-id", default="", help="Active story id for the docs receipt")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo).resolve()
    state_dir = repo_root / ".ai" / "dropbox" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    docs_truth_receipt_path = state_dir / "docs_truth_receipt.json"
    docs_sync_status_path = state_dir / "docs_sync_status.json"

    contradictions: list[dict[str, str]] = []
    docs_scanned = 0

    for relative in REQUIRED_DOCS:
        path = repo_root / relative
        if not path.exists():
            contradictions.append(
                {"file": relative, "message": "required guide or gap doc is missing"}
            )

    for path in sorted((repo_root / "docs").rglob("*.md")):
        docs_scanned += 1

    doc_owners_path = repo_root / ".ai" / "swarm" / "doc_owners.yaml"
    if not doc_owners_path.exists():
        contradictions.append(
            {"file": ".ai/swarm/doc_owners.yaml", "message": "docs routing map is missing"}
        )
    else:
        doc_owners = yaml.safe_load(doc_owners_path.read_text(encoding="utf-8"))
        review_paths: set[str] = set(doc_owners.get("always_review", []))
        for family in doc_owners.get("story_classes", {}).values():
            review_paths.update(family.get("review_paths", []))
        for family in doc_owners.get("layers", {}).values():
            review_paths.update(family.get("review_paths", []))
        for review_path in sorted(review_paths):
            if not (repo_root / review_path).exists():
                contradictions.append(
                    {
                        "file": ".ai/swarm/doc_owners.yaml",
                        "message": f"referenced docs surface does not exist: {review_path}",
                    }
                )

    for relative, snippets in FORBIDDEN_SNIPPETS.items():
        path = repo_root / relative
        if not path.exists():
            contradictions.append({"file": relative, "message": "required doc is missing"})
            continue
        contents = read_text(path)
        for snippet in snippets:
            if snippet in contents:
                contradictions.append(
                    {
                        "file": relative,
                        "message": f"stale claim still present: {snippet}",
                    }
                )

    for relative, snippets in REQUIRED_SNIPPETS.items():
        path = repo_root / relative
        if not path.exists():
            contradictions.append({"file": relative, "message": "required doc is missing"})
            continue
        contents = read_text(path)
        for snippet in snippets:
            if snippet not in contents:
                contradictions.append(
                    {
                        "file": relative,
                        "message": f"required current-truth language missing: {snippet}",
                    }
                )

    changed_docs = sorted({entry["file"] for entry in contradictions})
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    story_id = args.story_id
    receipt_id = f"docs_truth::{story_id or 'none'}::{generated_at}"
    status = "clean" if not contradictions else "blocked"

    receipt = {
        "receipt_id": receipt_id,
        "story_id": story_id,
        "status": status,
        "generated_at": generated_at,
        "docs_scanned": docs_scanned,
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "changed_docs_expected": changed_docs,
    }
    docs_truth_receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    sync_status = {
        "storyId": story_id,
        "status": status,
        "receiptId": receipt_id,
        "updatedAt": generated_at,
        "contradictionCount": len(contradictions),
        "changedDocs": changed_docs,
    }
    docs_sync_status_path.write_text(json.dumps(sync_status, indent=2) + "\n", encoding="utf-8")

    if contradictions:
        print(json.dumps(receipt, indent=2))
        return 1

    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
