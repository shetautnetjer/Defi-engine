"""Evidence rollup helpers for turning paper decisions into next experiments."""

from __future__ import annotations

from collections import Counter
from typing import Any

import orjson

from d5_trading_engine.config.settings import Settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import PaperPracticeDecisionV1

_FAMILY_BATCH_TYPES = {
    "strategy_runtime_mismatch": "strategy_runtime_mismatch_batch",
    "condition_threshold_overblocking": "condition_coverage_batch",
    "data_or_capture_readiness": "data_coverage_repair_batch",
    "policy_regime_eligibility": "policy_regime_eligibility_batch",
    "paper_profile_cooldown": "paper_profile_cadence_batch",
    "unknown_no_trade_surface": "no_trade_funnel_batch",
}

_FAMILY_PRIORITIES = {
    "strategy_runtime_mismatch": 0,
    "candidate_generation_failure": 1,
    "risk_overblocking": 2,
    "quote_fill_unavailability": 3,
    "condition_threshold_overblocking": 4,
    "data_or_capture_readiness": 5,
    "policy_regime_eligibility": 6,
    "paper_profile_cooldown": 7,
    "unknown_no_trade_surface": 99,
}

_REASON_PRIORITIES = {
    "strategy_target_not_runtime_long": 0,
    "strategy_regime_not_allowed": 1,
    "condition_confidence_below_profile_minimum": 2,
    "paper_ready_receipt_not_actionable": 3,
    "regime_not_allowed": 4,
    "profile_cooldown_active": 5,
}


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _family_from_reason(code: str) -> str:
    if code.startswith("strategy_target_not_runtime_long"):
        return "strategy_runtime_mismatch"
    if code.startswith("strategy_regime_not_allowed"):
        return "strategy_runtime_mismatch"
    if code == "condition_confidence_below_profile_minimum":
        return "condition_threshold_overblocking"
    if code == "paper_ready_receipt_not_actionable":
        return "data_or_capture_readiness"
    if code.startswith("regime_not_allowed"):
        return "policy_regime_eligibility"
    if code == "profile_cooldown_active":
        return "paper_profile_cooldown"
    return "unknown_no_trade_surface"


def _reason_priority(code: str) -> int:
    for prefix, priority in _REASON_PRIORITIES.items():
        if code.startswith(prefix):
            return priority
    return 99


def build_training_evidence_gap(settings: Settings) -> dict[str, Any]:
    """Summarize whether paper practice is creating comparable learning evidence."""
    session = get_session(settings)
    try:
        decisions = (
            session.query(PaperPracticeDecisionV1)
            .order_by(PaperPracticeDecisionV1.created_at.asc(), PaperPracticeDecisionV1.id.asc())
            .all()
        )
    finally:
        session.close()

    reason_counts: Counter[str] = Counter()
    family_counts: Counter[str] = Counter()
    no_trade_cycles = 0
    paper_filled_cycles = 0
    evidence_feedback_count = 0

    for decision in decisions:
        if decision.decision_type == "no_trade":
            no_trade_cycles += 1
        if decision.decision_type in {"paper_trade_opened", "paper_trade_closed"}:
            paper_filled_cycles += 1

        decision_payload = _load_json_object(decision.decision_payload_json)
        evidence_feedback = decision_payload.get("evidence_feedback")
        decision_families: set[str] = set()
        if isinstance(evidence_feedback, dict) and evidence_feedback:
            evidence_feedback_count += 1
            decision_families.add(
                str(
                    evidence_feedback.get("primary_failure_surface")
                    or "unknown_no_trade_surface"
                )
            )

        for reason_code in _load_json_list(decision.reason_codes_json):
            reason_counts[reason_code] += 1
            if decision.decision_type == "no_trade" and not evidence_feedback:
                decision_families.add(_family_from_reason(reason_code))

        for family in decision_families:
            family_counts[family] += 1

    decision_cycles = len(decisions)
    top_failure_families = [
        {
            "family": family,
            "count": count,
            "score": round(count / max(1, no_trade_cycles), 4),
        }
        for family, count in sorted(
            family_counts.items(),
            key=lambda item: (-item[1], _FAMILY_PRIORITIES.get(item[0], 99), item[0]),
        )
    ]
    selected_family = (
        top_failure_families[0]["family"]
        if top_failure_families
        else "unknown_no_trade_surface"
    )
    selected_batch_type = _FAMILY_BATCH_TYPES.get(selected_family, "no_trade_funnel_batch")
    top_reason_codes = [
        {"reason_code": code, "count": count}
        for code, count in sorted(
            reason_counts.items(),
            key=lambda item: (-item[1], _reason_priority(item[0]), item[0]),
        )
    ]

    return {
        "status": "completed",
        "primary_learning_gap": "proposals_not_being_converted_to_comparable_tests",
        "top_gap_surfaces": [item["family"] for item in top_failure_families[:3]],
        "top_failure_families": top_failure_families,
        "selected_batch_type": selected_batch_type,
        "recommended_batch_type": selected_batch_type,
        "selection_confidence": top_failure_families[0]["score"]
        if top_failure_families
        else 0.0,
        "falsification_required": True,
        "decision_funnel": {
            "decision_cycles": decision_cycles,
            "no_trade_cycles": no_trade_cycles,
            "paper_filled_cycles": paper_filled_cycles,
            "evidence_feedback_cycles": evidence_feedback_count,
        },
        "top_reason_codes": top_reason_codes,
        "recommended_next_action": (
            "Generate a tiny comparable experiment batch from the selected failure family, "
            "including one falsification candidate."
        ),
        "next_command": "d5 training evidence-gap --json",
    }
