"""Experiment-batch generation from ranked evidence-gap families."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings
from d5_trading_engine.reporting.proposals import create_improvement_proposal

_DEFAULT_REGISTRY: dict[str, Any] = {
    "version": "v1",
    "families": {
        "strategy_runtime_mismatch": {
            "batch_type": "strategy_runtime_mismatch_batch",
            "selection_goal": (
                "Test whether paper runtime is blocked because strategy candidates "
                "are incompatible with the currently observed long-friendly regime."
            ),
            "templates": [
                {
                    "template_id": "runtime_long_compatible_strategy_eval_v1",
                    "candidate_overlay_type": "candidate_strategy_policy_overlay_v1",
                    "target_surface": "strategy_policy",
                    "title": "Enable a long-compatible strategy-policy overlay in shadow",
                    "hypothesis": (
                        "If long-friendly regimes are repeatedly producing flat/no-trade "
                        "runtime targets, a bounded long-compatible strategy-policy overlay "
                        "should create comparable paper candidates without bypassing risk."
                    ),
                    "overlay": {
                        "base_policy": "policy_global_regime_trace_v1",
                        "changes": {
                            "long_friendly.shadow_enabled_strategy_families": [
                                "trend_continuation_long_v1",
                                "mean_reversion_long_v1",
                            ],
                            "runtime_effect": "shadow_or_research_only",
                        },
                    },
                    "test_command": "d5 run-strategy-eval governed-challengers-v1 --json",
                    "success_gate": {
                        "candidate_count_min": 1,
                        "requires_baseline_comparison": True,
                        "requires_no_runtime_promotion": True,
                    },
                    "falsification_candidate": False,
                },
                {
                    "template_id": "long_no_anomaly_veto_shadow_v1",
                    "candidate_overlay_type": "candidate_policy_overlay_v1",
                    "target_surface": "policy",
                    "title": "Isolate whether anomaly vetoes are suppressing long candidates",
                    "hypothesis": (
                        "If the candidate detector can find long-compatible setups only when "
                        "anomaly veto sensitivity is relaxed in shadow, the next test should "
                        "focus on risk/policy overblocking rather than strategy discovery."
                    ),
                    "overlay": {
                        "base_policy": "policy_global_regime_trace_v1",
                        "changes": {
                            "long_friendly.shadow_anomaly_veto_mode": "diagnostic_relaxed",
                            "risk_gate_bypass": False,
                            "runtime_effect": "shadow_only",
                        },
                    },
                    "test_command": "d5 diagnose gate-funnel --run latest --json",
                    "success_gate": {
                        "risk_gate_must_remain_final": True,
                        "requires_reason_code_histogram": True,
                    },
                    "falsification_candidate": False,
                },
                {
                    "template_id": "always_candidate_long_sanity_v1",
                    "candidate_overlay_type": "candidate_strategy_policy_overlay_v1",
                    "target_surface": "strategy_candidate_generation",
                    "title": "Falsify dead-candidate generator with always-candidate sanity lane",
                    "hypothesis": (
                        "If an always-candidate long sanity overlay still produces no "
                        "candidates, the failure is below policy selection and belongs in "
                        "candidate generation or data wiring."
                    ),
                    "overlay": {
                        "base_detector": "paper_runtime_strategy_selector",
                        "changes": {
                            "diagnostic_mode": "always_candidate_long",
                            "instrument_pair": "SOL/USDC",
                            "runtime_effect": "research_only",
                        },
                    },
                    "test_command": "d5 diagnose no-trades --run latest --window 300d --json",
                    "success_gate": {
                        "must_emit_candidate_rows": True,
                        "must_not_open_live_orders": True,
                    },
                    "falsification_candidate": True,
                },
            ],
        },
        "candidate_generation_failure": {
            "batch_type": "candidate_generation_failure_batch",
            "selection_goal": (
                "Prove the strategy detector can emit candidates before tuning policy or risk."
            ),
            "templates": [
                {
                    "template_id": "always_candidate_baseline_v1",
                    "candidate_overlay_type": "candidate_strategy_policy_overlay_v1",
                    "target_surface": "strategy_candidate_generation",
                    "title": "Run an always-candidate baseline",
                    "hypothesis": (
                        "A diagnostic always-candidate lane should create opportunity rows "
                        "if the runtime wiring is intact."
                    ),
                    "overlay": {
                        "base_detector": "paper_runtime_strategy_selector",
                        "changes": {
                            "diagnostic_mode": "always_candidate",
                            "runtime_effect": "research_only",
                        },
                    },
                    "test_command": "d5 diagnose no-trades --run latest --window 300d --json",
                    "success_gate": {"must_emit_candidate_rows": True},
                    "falsification_candidate": True,
                }
            ],
        },
        "risk_overblocking": {
            "batch_type": "risk_overblocking_batch",
            "selection_goal": (
                "Separate true unsafe risk rejects from missing data or stale quote failures."
            ),
            "templates": [
                {
                    "template_id": "risk_reason_breakdown_v1",
                    "candidate_overlay_type": "candidate_risk_overlay_v1",
                    "target_surface": "risk",
                    "title": "Break down risk rejection reasons",
                    "hypothesis": (
                        "A typed risk rejection histogram should show whether risk is "
                        "overblocking or correctly vetoing unsafe setups."
                    ),
                    "overlay": {
                        "base_risk": "risk_global_regime_gate_v1",
                        "changes": {"diagnostic_only": True, "runtime_effect": "research_only"},
                    },
                    "test_command": "d5 diagnose gate-funnel --run latest --json",
                    "success_gate": {"requires_risk_reason_histogram": True},
                    "falsification_candidate": True,
                }
            ],
        },
        "quote_fill_unavailability": {
            "batch_type": "quote_fill_unavailability_batch",
            "selection_goal": "Separate executable quote availability from strategy quality.",
            "templates": [
                {
                    "template_id": "quote_availability_audit_v1",
                    "candidate_overlay_type": "candidate_source_transform_overlay_v1",
                    "target_surface": "source_or_execution_fill",
                    "title": "Audit quote availability and staleness",
                    "hypothesis": (
                        "If quote gaps dominate no-trade decisions, source freshness must "
                        "be repaired before strategy comparisons matter."
                    ),
                    "overlay": {
                        "base_source": "jupiter_quote_snapshot",
                        "changes": {"diagnostic_only": True, "runtime_effect": "research_only"},
                    },
                    "test_command": "d5 diagnose gate-funnel --run latest --json",
                    "success_gate": {"requires_quote_missing_count": True},
                    "falsification_candidate": True,
                }
            ],
        },
    },
}


def load_failure_family_registry(settings: Settings) -> dict[str, Any]:
    """Load the machine-readable family registry, falling back to built-ins."""
    path = settings.repo_root / ".ai" / "policies" / "failure_family_registry.v1.json"
    try:
        payload = orjson.loads(path.read_bytes())
    except (FileNotFoundError, orjson.JSONDecodeError):
        return deepcopy(_DEFAULT_REGISTRY)
    return payload if isinstance(payload, dict) else deepcopy(_DEFAULT_REGISTRY)


def build_candidate_batch(
    *,
    settings: Settings,
    evidence_gap: dict[str, Any],
    batch_id: str,
    artifact_dir: Path,
) -> dict[str, Any]:
    """Build candidate overlay artifacts and advisory proposals from evidence."""
    registry = load_failure_family_registry(settings)
    families = registry.get("families") if isinstance(registry.get("families"), dict) else {}
    ranked_families = evidence_gap.get("top_failure_families") or []
    selected_family = (
        str(ranked_families[0].get("family"))
        if ranked_families and isinstance(ranked_families[0], dict)
        else "strategy_runtime_mismatch"
    )
    family_spec = families.get(selected_family) or families.get("strategy_runtime_mismatch") or {}
    selected_batch_type = str(
        family_spec.get("batch_type")
        or evidence_gap.get("selected_batch_type")
        or "strategy_runtime_mismatch_batch"
    )
    templates = (
        family_spec.get("templates")
        if isinstance(family_spec.get("templates"), list)
        else []
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    candidates_dir = artifact_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    candidates: list[dict[str, Any]] = []
    for index, template in enumerate(templates[:3], start=1):
        if not isinstance(template, dict):
            continue
        candidate_id = f"{batch_id}_candidate_{index:02d}"
        candidate = {
            "candidate_id": candidate_id,
            "batch_id": batch_id,
            "failure_family": selected_family,
            "batch_type": selected_batch_type,
            "runtime_effect": "research_shadow_only",
            "promotion_allowed": False,
            "requires_review": True,
            "created_at": utcnow().isoformat(),
            **deepcopy(template),
        }
        candidate_path = candidates_dir / f"candidate_{index:02d}.json"
        candidate_path.write_bytes(orjson.dumps(candidate, option=orjson.OPT_INDENT_2))
        proposal = create_improvement_proposal(
            artifact_dir=candidates_dir / f"candidate_{index:02d}_proposal",
            proposal_kind="candidate_overlay_experiment",
            source_owner_type="experiment_batch",
            source_owner_key=batch_id,
            governance_scope=str(candidate.get("target_surface") or "research_loop"),
            title=str(candidate["title"]),
            summary=(
                f"Candidate overlay `{candidate_id}` for `{selected_family}`. "
                "This is research/shadow evidence only and grants no runtime authority."
            ),
            hypothesis=str(candidate["hypothesis"]),
            next_test=str(candidate["test_command"]),
            metrics={
                "selection_confidence": float(
                    evidence_gap.get("selection_confidence") or 0.0
                ),
                "falsification_candidate": (
                    1.0 if candidate.get("falsification_candidate") else 0.0
                ),
            },
            reason_codes=[
                f"failure_family:{selected_family}",
                f"batch_type:{selected_batch_type}",
                "candidate_overlay_no_runtime_authority",
            ],
            settings=settings,
        )
        candidate["proposal_id"] = proposal["proposal_id"]
        candidate["artifact_path"] = str(candidate_path)
        candidate["proposal_artifact_dir"] = str(
            candidates_dir / f"candidate_{index:02d}_proposal"
        )
        candidate_path.write_bytes(orjson.dumps(candidate, option=orjson.OPT_INDENT_2))
        candidates.append(candidate)

    batch_selection = {
        "batch_id": batch_id,
        "selected_failure_family": selected_family,
        "selected_batch_type": selected_batch_type,
        "selection_confidence": evidence_gap.get("selection_confidence", 0.0),
        "ranked_failure_families": ranked_families,
        "rejected_alternatives": [
            item
            for item in ranked_families
            if isinstance(item, dict) and item.get("family") != selected_family
        ],
        "falsification_candidate_included": any(
            bool(candidate.get("falsification_candidate")) for candidate in candidates
        ),
    }
    return {
        "status": "completed",
        "run_id": batch_id,
        "selected_failure_family": selected_family,
        "selected_batch_type": selected_batch_type,
        "selection_confidence": batch_selection["selection_confidence"],
        "candidate_count": len(candidates),
        "runtime_effect": "research_shadow_only",
        "promotion_allowed": False,
        "falsification_candidate_included": batch_selection["falsification_candidate_included"],
        "falsification_required": bool(evidence_gap.get("falsification_required", True)),
        "decision_funnel": deepcopy(evidence_gap.get("decision_funnel") or {}),
        "primary_learning_gap": evidence_gap.get("primary_learning_gap", ""),
        "top_reason_codes": deepcopy(evidence_gap.get("top_reason_codes") or []),
        "selection_goal": family_spec.get("selection_goal", ""),
        "batch_selection": batch_selection,
        "candidates": candidates,
    }
