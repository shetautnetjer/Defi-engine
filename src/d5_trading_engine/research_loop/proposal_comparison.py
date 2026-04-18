"""Deterministic proposal comparison and bounded next-test selection."""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import orjson
from sqlalchemy import desc

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd
from d5_trading_engine.research_loop.proposal_review import ProposalReviewer
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ConditionGlobalRegimeSnapshotV1,
    ImprovementProposalV1,
    ProposalComparisonItemV1,
    ProposalComparisonV1,
    ProposalReviewV1,
    ProposalSupersessionV1,
)

_REVIEW_DECISION_RANKS = {
    "reviewed_accept": 2,
    "reviewed_hold": 1,
}
_MATURITY_RANKS = {
    "paper_cycle_follow_on": 3,
    "paper_profile_adjustment_follow_on": 3,
    "strategy_eval_follow_on": 2,
    "live_regime_cycle_follow_on": 2,
    "regime_model_compare_follow_on": 2,
    "label_program_follow_on": 1,
}
_DEFAULT_ELIGIBLE_DECISIONS = {"reviewed_accept", "reviewed_hold"}
_DEFAULT_EXCLUDED_STATUSES = {"reviewed_reject", "selected_next", "superseded"}


def _loads_json(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return orjson.loads(text)
    except orjson.JSONDecodeError:
        return default


def _median(values: list[float]) -> float:
    return float(statistics.median(values)) if values else 0.0


@dataclass
class _Candidate:
    proposal: ImprovementProposalV1
    latest_review: ProposalReviewV1 | None
    story_class: str
    stage: str
    source_artifact_path: str
    source_artifact_payload: dict[str, Any]
    review_decision: str
    semantic_regime: str
    macro_context_state: str
    condition_run_id: str
    slice_key: str
    maturity_rank: int
    decision_rank: int
    regime_fit_rank: int
    evidence_score: float
    evidence_tuple: tuple[float, ...]
    score_breakdown: dict[str, Any]
    eligible_for_selection: bool


class ProposalComparator:
    """Rank reviewed proposals and optionally choose the next bounded experiment."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._reviewer = ProposalReviewer(self.settings)

    def compare_proposals(
        self,
        *,
        proposal_ids: list[str] | None = None,
        proposal_kind: str | None = None,
        story_class: str | None = None,
        semantic_regime: str | None = None,
        choose_top: bool = False,
    ) -> dict[str, Any]:
        comparison_id = f"comparison_{uuid.uuid4().hex[:12]}"
        created_at = utcnow()
        session = get_session(self.settings)
        try:
            current_snapshot = (
                session.query(ConditionGlobalRegimeSnapshotV1)
                .order_by(
                    desc(ConditionGlobalRegimeSnapshotV1.bucket_start_utc),
                    desc(ConditionGlobalRegimeSnapshotV1.id),
                )
                .first()
            )
            current_context = {
                "semantic_regime": getattr(current_snapshot, "semantic_regime", "") or "",
                "macro_context_state": getattr(current_snapshot, "macro_context_state", "") or "",
                "condition_run_id": getattr(current_snapshot, "condition_run_id", "") or "",
            }

            proposals = self._load_proposals(
                session,
                proposal_ids=proposal_ids or [],
                proposal_kind=proposal_kind,
            )
            candidates = [
                candidate
                for candidate in (
                    self._build_candidate(session, proposal, current_context)
                    for proposal in proposals
                )
                if self._candidate_in_scope(
                    candidate,
                    requested_story_class=story_class,
                    requested_semantic_regime=semantic_regime,
                    explicit_ids=bool(proposal_ids),
                )
            ]

            ranked = sorted(candidates, key=self._sort_key)
            selected_candidate: _Candidate | None = None
            superseded_candidates: list[_Candidate] = []
            if choose_top:
                for candidate in ranked:
                    if candidate.eligible_for_selection:
                        selected_candidate = candidate
                        break
                if selected_candidate is not None:
                    superseded_candidates = [
                        candidate
                        for candidate in ranked
                        if candidate.proposal.proposal_id != selected_candidate.proposal.proposal_id
                        and candidate.proposal.proposal_kind
                        == selected_candidate.proposal.proposal_kind
                        and candidate.eligible_for_selection
                    ]
                    selected_candidate.proposal.status = "selected_next"
                    for candidate in superseded_candidates:
                        candidate.proposal.status = "superseded"

            comparison_row = ProposalComparisonV1(
                comparison_id=comparison_id,
                reviewer_kind="ai_reviewer",
                selection_mode="choose_top" if choose_top else "rank_only",
                comparison_scope_json=orjson.dumps(
                    {
                        "proposal_ids": proposal_ids or [],
                        "proposal_kind": proposal_kind or "",
                        "story_class": story_class or "",
                        "semantic_regime": semantic_regime or "",
                        "current_context": current_context,
                    }
                ).decode(),
                selected_proposal_id=(
                    selected_candidate.proposal.proposal_id if selected_candidate else None
                ),
                selected_review_id=(
                    selected_candidate.latest_review.review_id
                    if selected_candidate and selected_candidate.latest_review is not None
                    else None
                ),
                selected_slice_key=selected_candidate.slice_key if selected_candidate else None,
                created_at=created_at,
            )
            session.add(comparison_row)
            session.flush()

            same_kind_superseded = {
                candidate.proposal.proposal_id for candidate in superseded_candidates
            }
            comparison_items: list[ProposalComparisonItemV1] = []
            for candidate in ranked:
                comparison_items.append(
                    ProposalComparisonItemV1(
                        comparison_id=comparison_id,
                        proposal_id=candidate.proposal.proposal_id,
                        latest_review_id=(
                            candidate.latest_review.review_id
                            if candidate.latest_review is not None
                            else None
                        ),
                        proposal_kind=candidate.proposal.proposal_kind,
                        story_class=candidate.story_class or None,
                        stage=candidate.stage or None,
                        review_decision=candidate.review_decision,
                        slice_key=candidate.slice_key,
                        semantic_regime=candidate.semantic_regime or None,
                        macro_context_state=candidate.macro_context_state or None,
                        condition_run_id=candidate.condition_run_id or None,
                        maturity_rank=candidate.maturity_rank,
                        decision_rank=candidate.decision_rank,
                        regime_fit_rank=candidate.regime_fit_rank,
                        evidence_score=candidate.evidence_score,
                        score_breakdown_json=orjson.dumps(candidate.score_breakdown).decode(),
                        selected_flag=(
                            1
                            if selected_candidate is not None
                            and candidate.proposal.proposal_id
                            == selected_candidate.proposal.proposal_id
                            else 0
                        ),
                        superseded_flag=(
                            1 if candidate.proposal.proposal_id in same_kind_superseded else 0
                        ),
                        created_at=created_at,
                    )
                )
            session.add_all(comparison_items)

            supersession_rows: list[ProposalSupersessionV1] = []
            if selected_candidate is not None:
                for candidate in superseded_candidates:
                    supersession_rows.append(
                        ProposalSupersessionV1(
                            supersession_id=f"supersession_{uuid.uuid4().hex[:12]}",
                            comparison_id=comparison_id,
                            selected_proposal_id=selected_candidate.proposal.proposal_id,
                            superseded_proposal_id=candidate.proposal.proposal_id,
                            proposal_kind=selected_candidate.proposal.proposal_kind,
                            supersession_reason=(
                                "lower-ranked same-kind proposal in choose_top comparison"
                            ),
                            slice_key=candidate.slice_key,
                            created_at=created_at,
                        )
                    )
            if supersession_rows:
                session.add_all(supersession_rows)

            session.commit()
        finally:
            session.close()

        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "proposal_comparisons"
            / comparison_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        selected_payload = (
            self._candidate_payload(selected_candidate) if selected_candidate else None
        )
        comparison_payload = {
            "comparison_id": comparison_id,
            "selection_mode": "choose_top" if choose_top else "rank_only",
            "selected_proposal_id": (
                selected_candidate.proposal.proposal_id if selected_candidate else None
            ),
            "selected_review_id": (
                selected_candidate.latest_review.review_id
                if selected_candidate and selected_candidate.latest_review is not None
                else None
            ),
            "selected_slice_key": selected_candidate.slice_key if selected_candidate else None,
            "current_context": current_context,
            "scope": {
                "proposal_ids": proposal_ids or [],
                "proposal_kind": proposal_kind or "",
                "story_class": story_class or "",
                "semantic_regime": semantic_regime or "",
            },
            "ranked_items": [self._candidate_payload(candidate) for candidate in ranked],
            "selected_item": selected_payload,
            "superseded_proposal_ids": [
                candidate.proposal.proposal_id for candidate in superseded_candidates
            ],
            "created_at": created_at.isoformat(),
        }
        write_json_artifact(
            artifact_dir / "comparison.json",
            comparison_payload,
            owner_type="proposal_comparison",
            owner_key=comparison_id,
            artifact_type="proposal_comparison",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "comparison.qmd",
            render_qmd(
                "proposal_comparison.qmd",
                title="Proposal comparison",
                summary_lines=[
                    f"- comparison id: `{comparison_id}`",
                    f"- selection mode: `{'choose_top' if choose_top else 'rank_only'}`",
                    f"- current semantic regime: `{current_context['semantic_regime'] or 'unknown'}`",
                    f"- current macro context: `{current_context['macro_context_state'] or 'unknown'}`",
                    f"- selected proposal: `{selected_candidate.proposal.proposal_id if selected_candidate else 'none'}`",
                ],
                sections=[
                    (
                        "Scope",
                        [
                            f"- proposal ids: `{', '.join(proposal_ids or []) or 'default pool'}`",
                            f"- proposal kind: `{proposal_kind or 'any'}`",
                            f"- story class: `{story_class or 'any'}`",
                            f"- semantic regime filter: `{semantic_regime or 'any'}`",
                        ],
                    ),
                    (
                        "Ranked Proposals",
                        [
                            (
                                f"- `{index + 1}` `{candidate.proposal.proposal_id}` "
                                f"kind=`{candidate.proposal.proposal_kind}` "
                                f"decision=`{candidate.review_decision}` "
                                f"slice=`{candidate.slice_key}` "
                                f"evidence_score=`{candidate.evidence_score:.4f}`"
                            )
                            for index, candidate in enumerate(ranked)
                        ]
                        or ["- no proposals matched the requested comparison scope"],
                    ),
                    (
                        "Selected Next Test",
                        [
                            f"- proposal id: `{selected_candidate.proposal.proposal_id}`",
                            f"- review id: `{selected_candidate.latest_review.review_id if selected_candidate and selected_candidate.latest_review else ''}`",
                            f"- story class: `{selected_candidate.story_class}`",
                            f"- stage: `{selected_candidate.stage}`",
                            f"- summary: {selected_candidate.score_breakdown.get('selection_summary', '')}",
                        ]
                        if selected_candidate
                        else ["- no proposal was eligible for selection"],
                    ),
                    (
                        "Supersession History",
                        [
                            f"- `{candidate.proposal.proposal_id}` superseded by `{selected_candidate.proposal.proposal_id}`"
                            for candidate in superseded_candidates
                        ]
                        or ["- no supersession edges were written"],
                    ),
                ],
                generated_at=created_at,
            ),
            owner_type="proposal_comparison",
            owner_key=comparison_id,
            artifact_type="proposal_comparison_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

        receipt_path = (
            self.settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "research_proposal_priority_receipt.json"
        )
        receipt_payload = {
            "receipt_id": f"proposal_priority::{comparison_id}",
            "comparison_id": comparison_id,
            "selection_mode": "choose_top" if choose_top else "rank_only",
            "selected_proposal_id": (
                selected_candidate.proposal.proposal_id if selected_candidate else ""
            ),
            "selected_review_id": (
                selected_candidate.latest_review.review_id
                if selected_candidate and selected_candidate.latest_review is not None
                else ""
            ),
            "selected_story_class": selected_candidate.story_class if selected_candidate else "",
            "selected_stage": selected_candidate.stage if selected_candidate else "",
            "selected_slice_key": selected_candidate.slice_key if selected_candidate else "",
            "superseded_proposal_ids": [
                candidate.proposal.proposal_id for candidate in superseded_candidates
            ],
            "summary": (
                selected_candidate.score_breakdown.get("selection_summary", "")
                if selected_candidate
                else "No proposal was eligible for bounded next-test selection."
            ),
            "metrics": (
                {
                    "maturity_rank": selected_candidate.maturity_rank,
                    "decision_rank": selected_candidate.decision_rank,
                    "regime_fit_rank": selected_candidate.regime_fit_rank,
                    "evidence_score": selected_candidate.evidence_score,
                }
                if selected_candidate
                else {}
            ),
            "updated_at": created_at.isoformat(),
        }
        write_json_artifact(
            receipt_path,
            receipt_payload,
            owner_type="proposal_comparison",
            owner_key=comparison_id,
            artifact_type="research_proposal_priority_receipt",
            settings=self.settings,
        )

        return {
            "comparison_id": comparison_id,
            "artifact_dir": str(artifact_dir),
            "receipt_path": str(receipt_path),
            "selected_proposal_id": receipt_payload["selected_proposal_id"],
            "selected_review_id": receipt_payload["selected_review_id"],
            "superseded_proposal_ids": receipt_payload["superseded_proposal_ids"],
            "ranked_count": len(ranked),
        }

    def _load_proposals(
        self,
        session,
        *,
        proposal_ids: list[str],
        proposal_kind: str | None,
    ) -> list[ImprovementProposalV1]:
        query = session.query(ImprovementProposalV1)
        if proposal_ids:
            rows = query.filter(ImprovementProposalV1.proposal_id.in_(proposal_ids)).all()
            by_id = {row.proposal_id: row for row in rows}
            return [by_id[proposal_id] for proposal_id in proposal_ids if proposal_id in by_id]

        query = query.filter_by(runtime_effect="advisory_only")
        if proposal_kind:
            query = query.filter_by(proposal_kind=proposal_kind)
        return (
            query.filter(~ImprovementProposalV1.status.in_(_DEFAULT_EXCLUDED_STATUSES))
            .order_by(ImprovementProposalV1.created_at.desc(), ImprovementProposalV1.id.desc())
            .all()
        )

    def _build_candidate(
        self,
        session,
        proposal: ImprovementProposalV1,
        current_context: dict[str, str],
    ) -> _Candidate:
        source_artifacts = (
            session.query(ArtifactReference)
            .filter_by(
                owner_type=proposal.source_owner_type,
                owner_key=proposal.source_owner_key,
            )
            .order_by(ArtifactReference.created_at.asc(), ArtifactReference.id.asc())
            .all()
        )
        source_context = self._reviewer._build_source_context(session, proposal, source_artifacts)
        latest_review = (
            session.query(ProposalReviewV1)
            .filter_by(proposal_id=proposal.proposal_id)
            .order_by(desc(ProposalReviewV1.created_at), desc(ProposalReviewV1.id))
            .first()
        )
        review_scope = (
            _loads_json(latest_review.regime_scope_json, {}) if latest_review is not None else {}
        )
        condition_scope = (
            _loads_json(latest_review.condition_scope_json, {})
            if latest_review is not None
            else {}
        )
        review_decision = latest_review.decision if latest_review is not None else "missing_review_truth"
        semantic_regime = str(
            review_scope.get("semantic_regime")
            or source_context["regime_scope"].get("semantic_regime")
            or ""
        )
        macro_context_state = str(
            review_scope.get("macro_context_state")
            or source_context["regime_scope"].get("macro_context_state")
            or ""
        )
        condition_run_id = str(
            condition_scope.get("condition_run_id")
            or source_context["condition_scope"].get("condition_run_id")
            or ""
        )
        slice_key = "|".join(
            [
                proposal.proposal_kind,
                semantic_regime or "unknown",
                macro_context_state or "unknown",
                condition_run_id or "unknown",
            ]
        )

        primary_artifact_payload = {}
        source_artifact_path = str(source_context.get("source_artifact_path") or "")
        if source_artifact_path:
            artifact_path = Path(source_artifact_path)
            if artifact_path.exists():
                primary_artifact_payload = _loads_json(artifact_path.read_text(encoding="utf-8"), {})

        maturity_rank = _MATURITY_RANKS.get(proposal.proposal_kind, 0)
        decision_rank = _REVIEW_DECISION_RANKS.get(review_decision, 0)
        regime_fit_rank = self._regime_fit_rank(
            proposal_kind=proposal.proposal_kind,
            semantic_regime=semantic_regime,
            current_semantic_regime=current_context["semantic_regime"],
            source_context=source_context,
        )
        evidence_tuple, evidence_score, evidence_details = self._evidence_rank(
            proposal=proposal,
            source_context=source_context,
            primary_artifact_payload=primary_artifact_payload,
        )
        eligible_for_selection = latest_review is not None and review_decision in _DEFAULT_ELIGIBLE_DECISIONS
        score_breakdown = {
            "maturity_rank": maturity_rank,
            "decision_rank": decision_rank,
            "regime_fit_rank": regime_fit_rank,
            "evidence_tuple": evidence_tuple,
            "evidence_score": evidence_score,
            "evidence_details": evidence_details,
            "reason_codes": (
                _loads_json(latest_review.reason_codes_json, [])
                if latest_review is not None
                else ["missing_review_truth"]
            ),
            "selection_summary": (
                f"{proposal.proposal_kind} in {semantic_regime or 'unknown_regime'} "
                f"ranked with maturity={maturity_rank}, decision={decision_rank}, "
                f"regime_fit={regime_fit_rank}."
            ),
        }
        return _Candidate(
            proposal=proposal,
            latest_review=latest_review,
            story_class=str(source_context.get("story_class") or ""),
            stage=str(source_context.get("stage") or ""),
            source_artifact_path=source_artifact_path,
            source_artifact_payload=primary_artifact_payload,
            review_decision=review_decision,
            semantic_regime=semantic_regime,
            macro_context_state=macro_context_state,
            condition_run_id=condition_run_id,
            slice_key=slice_key,
            maturity_rank=maturity_rank,
            decision_rank=decision_rank,
            regime_fit_rank=regime_fit_rank,
            evidence_score=evidence_score,
            evidence_tuple=evidence_tuple,
            score_breakdown=score_breakdown,
            eligible_for_selection=eligible_for_selection,
        )

    def _candidate_in_scope(
        self,
        candidate: _Candidate,
        *,
        requested_story_class: str | None,
        requested_semantic_regime: str | None,
        explicit_ids: bool,
    ) -> bool:
        if requested_story_class and candidate.story_class != requested_story_class:
            return False
        if requested_semantic_regime and candidate.semantic_regime != requested_semantic_regime:
            return False
        if explicit_ids:
            return True
        return candidate.review_decision in _DEFAULT_ELIGIBLE_DECISIONS

    def _regime_fit_rank(
        self,
        *,
        proposal_kind: str,
        semantic_regime: str,
        current_semantic_regime: str,
        source_context: dict[str, Any],
    ) -> int:
        if semantic_regime and current_semantic_regime and semantic_regime == current_semantic_regime:
            return 3

        if proposal_kind == "paper_cycle_follow_on":
            regime_aligned = float(source_context["source_metrics"].get("regime_aligned", 0.0))
            if regime_aligned >= 1.0:
                return 2
        if semantic_regime or source_context["condition_scope"].get("condition_run_id"):
            return 1
        return 0

    def _evidence_rank(
        self,
        *,
        proposal: ImprovementProposalV1,
        source_context: dict[str, Any],
        primary_artifact_payload: dict[str, Any],
    ) -> tuple[tuple[float, ...], float, dict[str, Any]]:
        proposal_metrics = _loads_json(proposal.metrics_json, {})
        if proposal.proposal_kind == "paper_cycle_follow_on":
            alignment = primary_artifact_payload.get("strategy_alignment", {})
            portfolio_state = primary_artifact_payload.get("portfolio_state", {})
            source_metrics = source_context["source_metrics"]
            regime_aligned = float(
                alignment.get("regime_aligned", proposal_metrics.get("regime_aligned", 0.0))
                or 0.0
            )
            filled = float(proposal_metrics.get("filled", 0.0) or 0.0)
            pnl = float(source_metrics.get("paper_realized_pnl_usdc", 0.0) or 0.0)
            equity = float(
                portfolio_state.get("total_value_usdc", proposal_metrics.get("equity_usdc", 0.0))
                or 0.0
            )
            evidence_tuple = (regime_aligned, filled, pnl, equity)
            evidence_score = (regime_aligned * 1000.0) + (filled * 100.0) + (pnl * 10.0) + equity
            return evidence_tuple, evidence_score, {
                "regime_aligned": regime_aligned,
                "filled": filled,
                "paper_realized_pnl_usdc": pnl,
                "equity_usdc": equity,
            }

        if proposal.proposal_kind == "regime_model_compare_follow_on":
            source_metrics = source_context["source_metrics"]
            artifact_recommendation = primary_artifact_payload.get("recommendation", {})
            recommended_is_statsmodels = float(
                artifact_recommendation.get(
                    "recommended_candidate",
                    "hmm",
                )
                == "statsmodels"
            )
            statsmodels_fit_success = float(
                source_metrics.get(
                    "statsmodels_fit_success",
                    proposal_metrics.get("statsmodels_fit_success", 0.0),
                )
                or 0.0
            )
            semantic_coverage = float(
                source_metrics.get(
                    "best_semantic_mapping_coverage",
                    proposal_metrics.get("best_semantic_mapping_coverage", 0.0),
                )
                or 0.0
            )
            adjacent_flip_rate = float(
                source_metrics.get(
                    "best_adjacent_flip_rate",
                    proposal_metrics.get("best_adjacent_flip_rate", 1.0),
                )
                or 1.0
            )
            feature_bucket_rows = float(
                source_metrics.get(
                    "feature_bucket_rows",
                    proposal_metrics.get("feature_bucket_rows", 0.0),
                )
                or 0.0
            )
            evidence_tuple = (
                statsmodels_fit_success,
                semantic_coverage,
                -adjacent_flip_rate,
                feature_bucket_rows,
                recommended_is_statsmodels,
            )
            evidence_score = (
                statsmodels_fit_success * 1000.0
                + semantic_coverage * 100.0
                - adjacent_flip_rate * 10.0
                + feature_bucket_rows
                + recommended_is_statsmodels
            )
            return evidence_tuple, evidence_score, {
                "statsmodels_fit_success": statsmodels_fit_success,
                "best_semantic_mapping_coverage": semantic_coverage,
                "best_adjacent_flip_rate": adjacent_flip_rate,
                "feature_bucket_rows": feature_bucket_rows,
                "recommended_is_statsmodels": recommended_is_statsmodels,
            }

        if proposal.proposal_kind == "live_regime_cycle_follow_on":
            paper_ready = primary_artifact_payload.get("paper_ready_receipt", {})
            source_metrics = source_context["source_metrics"]
            quote_present = float(
                paper_ready.get(
                    "quote_snapshot_id",
                    proposal_metrics.get("paper_ready_quote_present", 0.0),
                )
                is not None
            )
            policy_eligible = float(
                paper_ready.get("policy_state", "") == "eligible_long"
                or proposal_metrics.get("policy_eligible_long", 0.0)
            )
            risk_allowed = float(
                paper_ready.get("risk_state", "") == "allowed"
                or proposal_metrics.get("risk_allowed", 0.0)
            )
            global_feature_rows = float(
                source_metrics.get(
                    "global_feature_rows",
                    proposal_metrics.get("global_feature_rows", 0.0),
                )
                or 0.0
            )
            evidence_tuple = (
                quote_present,
                policy_eligible,
                risk_allowed,
                global_feature_rows,
            )
            evidence_score = (
                quote_present * 1000.0
                + policy_eligible * 100.0
                + risk_allowed * 10.0
                + global_feature_rows
            )
            return evidence_tuple, evidence_score, {
                "paper_ready_quote_present": quote_present,
                "policy_eligible_long": policy_eligible,
                "risk_allowed": risk_allowed,
                "global_feature_rows": global_feature_rows,
            }

        if proposal.proposal_kind == "paper_profile_adjustment_follow_on":
            source_metrics = source_context["source_metrics"]
            patch_keys = primary_artifact_payload.get("patch_keys") or []
            patch_size = float(len(patch_keys) or proposal_metrics.get("patch_size", 0.0) or 0.0)
            realized_pnl_usdc = float(
                source_metrics.get(
                    "paper_realized_pnl_usdc",
                    proposal_metrics.get("realized_pnl_usdc", 0.0),
                )
                or 0.0
            )
            realized_pnl_bps = float(proposal_metrics.get("realized_pnl_bps", 0.0) or 0.0)
            bars_held = float(proposal_metrics.get("bars_held", 0.0) or 0.0)
            evidence_tuple = (
                realized_pnl_usdc,
                realized_pnl_bps,
                -patch_size,
                -bars_held,
            )
            evidence_score = (
                realized_pnl_usdc * 100.0
                + realized_pnl_bps
                - patch_size * 5.0
                - bars_held * 0.1
            )
            return evidence_tuple, evidence_score, {
                "realized_pnl_usdc": realized_pnl_usdc,
                "realized_pnl_bps": realized_pnl_bps,
                "patch_size": patch_size,
                "bars_held": bars_held,
            }

        families = primary_artifact_payload.get("families")
        if isinstance(families, dict):
            if proposal.proposal_kind == "strategy_eval_follow_on":
                top_family = str(primary_artifact_payload.get("top_family") or "")
                family_metrics = families.get(top_family, {}) if top_family else {}
                eligible = 1.0 if family_metrics.get("eligible") else 0.0
                positive_expectancy = float(family_metrics.get("positive_expectancy") or 0.0)
                xgb_accuracy = float(family_metrics.get("xgb_accuracy") or 0.0)
                xgb_auc = float(family_metrics.get("xgb_auc") or 0.0)
                evidence_tuple = (
                    eligible,
                    positive_expectancy,
                    xgb_accuracy,
                    xgb_auc,
                )
                evidence_score = (
                    eligible * 1000.0
                    + positive_expectancy * 100.0
                    + xgb_accuracy * 10.0
                    + xgb_auc
                )
                return evidence_tuple, evidence_score, {
                    "top_family": top_family,
                    "eligible": eligible,
                    "positive_expectancy": positive_expectancy,
                    "xgb_accuracy": xgb_accuracy,
                    "xgb_auc": xgb_auc,
                }

            source_metrics = source_context["source_metrics"]
            eligible_count = sum(1 for metrics in families.values() if metrics.get("eligible"))
            if eligible_count <= 0:
                eligible_count = int(proposal_metrics.get("eligible_family_count", 0) or 0)

            valid_coverages = [
                float(metrics["valid_coverage"])
                for metrics in families.values()
                if metrics.get("valid_coverage") is not None
            ]
            if not valid_coverages:
                valid_coverages = [
                    float(value or 0.0)
                    for name, value in source_metrics.items()
                    if name.endswith("_valid_coverage")
                ]

            invalid_rates = [
                float(metrics["invalid_rate"])
                for metrics in families.values()
                if metrics.get("invalid_rate") is not None
            ]
            if not invalid_rates:
                invalid_rates = [
                    float(value or 1.0)
                    for name, value in source_metrics.items()
                    if name.endswith("_invalid_rate")
                ]

            low_conf_rates = [
                float(metrics["low_confidence_rate"])
                for metrics in families.values()
                if metrics.get("low_confidence_rate") is not None
            ]
            if not low_conf_rates:
                low_conf_rates = [
                    float(value or 1.0)
                    for name, value in source_metrics.items()
                    if name.endswith("_low_confidence_rate")
                ]
            valid_coverage = _median(valid_coverages)
            invalid_rate = _median(invalid_rates)
            low_confidence_rate = _median(low_conf_rates)
            evidence_tuple = (
                float(eligible_count),
                valid_coverage,
                -invalid_rate,
                -low_confidence_rate,
            )
            evidence_score = (
                eligible_count * 1000.0
                + valid_coverage * 100.0
                - invalid_rate * 10.0
                - low_confidence_rate * 10.0
            )
            return evidence_tuple, evidence_score, {
                "eligible_family_count": eligible_count,
                "median_valid_coverage": valid_coverage,
                "median_invalid_rate": invalid_rate,
                "median_low_confidence_rate": low_confidence_rate,
            }

        if proposal.proposal_kind == "strategy_eval_follow_on":
            source_metrics = source_context["source_metrics"]
            positive_expectancy = max(
                [
                    float(value or 0.0)
                    for name, value in source_metrics.items()
                    if name.endswith("_positive_expectancy")
                ]
                or [float(proposal_metrics.get("positive_expectancy", 0.0) or 0.0)]
            )
            xgb_accuracy = max(
                [
                    float(value or 0.0)
                    for name, value in source_metrics.items()
                    if name.endswith("_xgb_accuracy")
                ]
                or [0.0]
            )
            xgb_auc = max(
                [
                    float(value or 0.0)
                    for name, value in source_metrics.items()
                    if name.endswith("_xgb_auc")
                ]
                or [0.0]
            )
            eligible = 1.0 if positive_expectancy > 0 else 0.0
            evidence_tuple = (eligible, positive_expectancy, xgb_accuracy, xgb_auc)
            evidence_score = (
                eligible * 1000.0
                + positive_expectancy * 100.0
                + xgb_accuracy * 10.0
                + xgb_auc
            )
            return evidence_tuple, evidence_score, {
                "eligible": eligible,
                "positive_expectancy": positive_expectancy,
                "xgb_accuracy": xgb_accuracy,
                "xgb_auc": xgb_auc,
            }

        source_metrics = source_context["source_metrics"]
        eligible_count = int(proposal_metrics.get("eligible_family_count", 0) or 0)
        valid_coverages = [
            float(value or 0.0)
            for name, value in source_metrics.items()
            if name.endswith("_valid_coverage")
        ]
        invalid_rates = [
            float(value or 1.0)
            for name, value in source_metrics.items()
            if name.endswith("_invalid_rate")
        ]
        low_conf_rates = [
            float(value or 1.0)
            for name, value in source_metrics.items()
            if name.endswith("_low_confidence_rate")
        ]
        valid_coverage = _median(valid_coverages)
        invalid_rate = _median(invalid_rates)
        low_confidence_rate = _median(low_conf_rates)
        evidence_tuple = (
            float(eligible_count),
            valid_coverage,
            -invalid_rate,
            -low_confidence_rate,
        )
        evidence_score = (
            eligible_count * 1000.0
            + valid_coverage * 100.0
            - invalid_rate * 10.0
            - low_confidence_rate * 10.0
        )
        return evidence_tuple, evidence_score, {
            "eligible_family_count": eligible_count,
            "median_valid_coverage": valid_coverage,
            "median_invalid_rate": invalid_rate,
            "median_low_confidence_rate": low_confidence_rate,
        }

    def _sort_key(self, candidate: _Candidate) -> tuple[Any, ...]:
        review_created_at = (
            candidate.latest_review.created_at.timestamp()
            if candidate.latest_review is not None and candidate.latest_review.created_at is not None
            else 0.0
        )
        proposal_created_at = (
            candidate.proposal.created_at.timestamp()
            if candidate.proposal.created_at is not None
            else 0.0
        )
        inverted_evidence = tuple(-value for value in candidate.evidence_tuple)
        return (
            -candidate.maturity_rank,
            -candidate.decision_rank,
            -candidate.regime_fit_rank,
            *inverted_evidence,
            -review_created_at,
            -proposal_created_at,
            candidate.proposal.proposal_id,
        )

    def _candidate_payload(self, candidate: _Candidate | None) -> dict[str, Any] | None:
        if candidate is None:
            return None
        return {
            "proposal_id": candidate.proposal.proposal_id,
            "proposal_kind": candidate.proposal.proposal_kind,
            "status": candidate.proposal.status,
            "review_id": candidate.latest_review.review_id if candidate.latest_review else "",
            "review_decision": candidate.review_decision,
            "story_class": candidate.story_class,
            "stage": candidate.stage,
            "slice_key": candidate.slice_key,
            "semantic_regime": candidate.semantic_regime,
            "macro_context_state": candidate.macro_context_state,
            "condition_run_id": candidate.condition_run_id,
            "maturity_rank": candidate.maturity_rank,
            "decision_rank": candidate.decision_rank,
            "regime_fit_rank": candidate.regime_fit_rank,
            "evidence_score": candidate.evidence_score,
            "source_artifact_path": candidate.source_artifact_path,
            "score_breakdown": candidate.score_breakdown,
            "eligible_for_selection": candidate.eligible_for_selection,
        }
