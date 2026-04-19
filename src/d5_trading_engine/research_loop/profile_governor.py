"""Thin evidence-weighted profile governor for trader autoresearch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PREFERRED_POLICY_PATH = Path(".ai/policies/profile_router_policy.v1.json")
_PREFERRED_SCORECARD_SCHEMA_PATH = Path(".ai/schemas/meta_governor_scorecard.schema.json")
_PREFERRED_DECISION_SCHEMA_PATH = Path(".ai/schemas/profile_governor_decision.schema.json")
_PREFERRED_PROMPT_PATH = Path(".ai/prompts/profile_governor_turn.md")

GovernorAction = Literal[
    "SELECT_PROFILE",
    "BLEND_PROFILES",
    "NO_TRADE",
    "SHADOW_ONLY",
    "NEED_MORE_EVIDENCE",
    "RETIRE_PROFILE",
]
EvidenceMaturity = Literal[
    "feature_only",
    "condition_only",
    "label_program",
    "strategy_eval",
    "paper_cycle",
]
NeutralValidationState = Literal[
    "confirmed",
    "pending",
    "profile_biased",
    "failed",
]


class ScoringWeights(BaseModel):
    out_of_sample: float
    paper: float
    stability: float
    regime_fit: float
    cost_penalty: float
    decay_penalty: float
    complexity_penalty: float


class GovernorThresholds(BaseModel):
    min_select_score: float
    min_blend_score: float
    max_blend_gap: float
    high_disagreement_index: float
    retire_below_score: float


class ProfileGovernorPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    version: str
    description: str
    scoring_weights: ScoringWeights
    evidence_multipliers: dict[EvidenceMaturity, float]
    thresholds: GovernorThresholds
    actions: list[GovernorAction]


class GovernorCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    profile_name: str
    evidence_maturity: EvidenceMaturity
    out_of_sample_score: float = 0.0
    paper_score: float = 0.0
    stability_score: float = 0.0
    regime_fit_score: float = 0.0
    cost_penalty: float = 0.0
    decay_penalty: float = 0.0
    complexity_penalty: float = 0.0
    disagreement_index: float = Field(default=0.0, ge=0.0, le=1.0)
    eligible_for_selection: bool = True
    profile_neutral_validation_state: NeutralValidationState = "pending"
    reason_codes: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


def _project_fallback(path: Path) -> Path:
    return (_PROJECT_ROOT / path).resolve()


def _resolve_path(repo_root: Path, relative_path: Path) -> Path:
    preferred = (repo_root / relative_path).resolve()
    if preferred.exists():
        return preferred
    fallback = _project_fallback(relative_path)
    return fallback if fallback.exists() else preferred


def resolve_profile_governor_policy_path(repo_root: Path) -> Path:
    return _resolve_path(repo_root, _PREFERRED_POLICY_PATH)


def resolve_profile_governor_scorecard_schema_path(repo_root: Path) -> Path:
    return _resolve_path(repo_root, _PREFERRED_SCORECARD_SCHEMA_PATH)


def resolve_profile_governor_decision_schema_path(repo_root: Path) -> Path:
    return _resolve_path(repo_root, _PREFERRED_DECISION_SCHEMA_PATH)


def resolve_profile_governor_prompt_path(repo_root: Path) -> Path:
    return _resolve_path(repo_root, _PREFERRED_PROMPT_PATH)


def load_profile_governor_policy(repo_root: Path) -> ProfileGovernorPolicy:
    policy_path = resolve_profile_governor_policy_path(repo_root)
    if not policy_path.exists():
        raise RuntimeError(f"Profile governor policy not found at {policy_path}")
    try:
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid profile governor policy JSON at {policy_path}") from exc
    try:
        return ProfileGovernorPolicy.model_validate(payload)
    except ValidationError as exc:
        raise RuntimeError(f"Invalid profile governor policy payload at {policy_path}") from exc


class ProfileGovernor:
    """Simple evidence-weighted router over profile-shaped candidates."""

    def __init__(self, *, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.policy = load_profile_governor_policy(repo_root)

    def evaluate_candidates(
        self,
        candidates: list[GovernorCandidate],
        *,
        selected_research_profile_name: str,
    ) -> dict[str, Any]:
        scored_candidates = [self._score_candidate(candidate) for candidate in candidates]
        ranked = sorted(scored_candidates, key=lambda item: item["score"], reverse=True)
        disagreement = self._disagreement(ranked)
        governor_action, reason_codes, selected_candidate, blend_candidates = self._select_action(
            ranked,
            disagreement=disagreement,
        )

        selected_candidate_id = selected_candidate["candidate_id"] if selected_candidate else ""
        selected_profile_name = selected_candidate["profile_name"] if selected_candidate else ""
        scorecard = {
            "policy_id": self.policy.policy_id,
            "selected_research_profile_name": selected_research_profile_name,
            "candidate_count": len(candidates),
            "disagreement_index": disagreement["index"],
            "disagreement_classification": disagreement["classification"],
            "disagreement_reason_codes": disagreement["reason_codes"],
            "ranking": [item["candidate_id"] for item in ranked],
            "profile_scores": ranked,
        }
        return {
            "governor_policy_id": self.policy.policy_id,
            "governor_action": governor_action,
            "governor_reason_codes": reason_codes,
            "selected_candidate_id": selected_candidate_id,
            "selected_profile_name": selected_profile_name,
            "blend_candidate_ids": [item["candidate_id"] for item in blend_candidates],
            "governor_scorecard": scorecard,
        }

    def _score_candidate(self, candidate: GovernorCandidate) -> dict[str, Any]:
        weights = self.policy.scoring_weights
        evidence_multiplier = self.policy.evidence_multipliers.get(candidate.evidence_maturity, 0.5)
        validation_bonus = 0.0
        if candidate.profile_neutral_validation_state == "confirmed":
            validation_bonus = 8.0
        elif candidate.profile_neutral_validation_state == "pending":
            validation_bonus = 2.0
        raw_score = (
            (weights.out_of_sample * candidate.out_of_sample_score)
            + (weights.paper * candidate.paper_score)
            + (weights.stability * candidate.stability_score)
            + (weights.regime_fit * candidate.regime_fit_score)
            - (weights.cost_penalty * candidate.cost_penalty)
            - (weights.decay_penalty * candidate.decay_penalty)
            - (weights.complexity_penalty * candidate.complexity_penalty)
            + validation_bonus
        )
        score = round(raw_score * evidence_multiplier, 4)
        components = {
            "out_of_sample": round(weights.out_of_sample * candidate.out_of_sample_score, 4),
            "paper": round(weights.paper * candidate.paper_score, 4),
            "stability": round(weights.stability * candidate.stability_score, 4),
            "regime_fit": round(weights.regime_fit * candidate.regime_fit_score, 4),
            "cost_penalty": round(weights.cost_penalty * candidate.cost_penalty, 4),
            "decay_penalty": round(weights.decay_penalty * candidate.decay_penalty, 4),
            "complexity_penalty": round(weights.complexity_penalty * candidate.complexity_penalty, 4),
            "evidence_multiplier": round(evidence_multiplier, 4),
            "profile_neutral_validation_bonus": round(validation_bonus, 4),
        }
        eligible = candidate.eligible_for_selection
        reason_codes = list(candidate.reason_codes)
        if candidate.profile_neutral_validation_state == "failed":
            eligible = False
            if "profile_neutral_validation_failed" not in reason_codes:
                reason_codes.append("profile_neutral_validation_failed")
        return {
            "candidate_id": candidate.candidate_id,
            "profile_name": candidate.profile_name,
            "evidence_maturity": candidate.evidence_maturity,
            "score": score,
            "eligible": eligible,
            "components": components,
            "disagreement_index": candidate.disagreement_index,
            "profile_neutral_validation_state": candidate.profile_neutral_validation_state,
            "reason_codes": reason_codes,
            "evidence_refs": list(candidate.evidence_refs),
            "details": dict(candidate.details),
        }

    def _disagreement(self, ranked: list[dict[str, Any]]) -> dict[str, Any]:
        if not ranked:
            return {
                "index": 0.0,
                "classification": "low",
                "reason_codes": ["no_candidates"],
            }
        index = round(
            max(float(item.get("disagreement_index", 0.0) or 0.0) for item in ranked),
            4,
        )
        classification = "low"
        if index >= self.policy.thresholds.high_disagreement_index:
            classification = "high"
        elif index >= (self.policy.thresholds.high_disagreement_index / 2.0):
            classification = "medium"
        return {
            "index": index,
            "classification": classification,
            "reason_codes": [f"score_dispersion_{classification}"],
        }

    def _select_action(
        self,
        ranked: list[dict[str, Any]],
        *,
        disagreement: dict[str, Any],
    ) -> tuple[GovernorAction, list[str], dict[str, Any] | None, list[dict[str, Any]]]:
        eligible = [item for item in ranked if item["eligible"]]
        if not eligible:
            return "NEED_MORE_EVIDENCE", ["no_eligible_profiles"], None, []

        top = eligible[0]
        second = eligible[1] if len(eligible) > 1 else None
        if disagreement["classification"] == "high":
            return "NO_TRADE", ["high_profile_disagreement"], top, []

        if (
            second is not None
            and top["profile_neutral_validation_state"] == "confirmed"
            and second["profile_neutral_validation_state"] == "confirmed"
            and top["score"] >= self.policy.thresholds.min_blend_score
            and second["score"] >= self.policy.thresholds.min_blend_score
            and abs(top["score"] - second["score"]) <= self.policy.thresholds.max_blend_gap
            and top["profile_name"] != second["profile_name"]
        ):
            return (
                "BLEND_PROFILES",
                ["top_two_profiles_close_and_above_blend_threshold"],
                top,
                [top, second],
            )

        if top["score"] >= self.policy.thresholds.min_select_score:
            if top["profile_neutral_validation_state"] == "confirmed":
                return "SELECT_PROFILE", ["top_profile_above_select_threshold"], top, []
            return "SHADOW_ONLY", ["profile_neutral_confirmation_required"], top, []

        if top["score"] < self.policy.thresholds.retire_below_score:
            return "RETIRE_PROFILE", ["top_profile_below_retire_threshold"], top, []

        if top["profile_neutral_validation_state"] != "confirmed":
            return "NEED_MORE_EVIDENCE", ["profile_neutral_confirmation_required"], top, []

        return "SHADOW_ONLY", ["best_candidate_below_select_threshold"], top, []
