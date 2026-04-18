"""Deterministic advisory proposal review flow."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import orjson
from sqlalchemy import desc

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ConditionGlobalRegimeSnapshotV1,
    ExperimentMetric,
    ExperimentRun,
    ImprovementProposalV1,
    PaperFill,
    PaperSession,
    PaperSessionReport,
    PolicyGlobalRegimeTraceV1,
    ProposalReviewV1,
    RiskGlobalRegimeGateV1,
)

_UNSAFE_RUNTIME_PHRASES = (
    "live trading",
    "live trade",
    "route live",
    "place live",
    "wallet signing",
    "private key",
    "disable risk",
    "loosen risk",
    "weaken risk",
    "runtime authority",
    "auto-promote",
    "autopromotion",
)
_SUPPORTED_GOVERNANCE_SCOPES = {"research_loop", "paper_runtime"}
_SOURCE_ARTIFACT_PRIORITY = (
    "regime_model_compare_summary",
    "label_program_candidate",
    "strategy_challenger_report",
    "paper_cycle_summary",
)
_PROPOSAL_KIND_HINTS = {
    "regime_model_compare_follow_on": {
        "story_class": "regime_model_compare",
        "source_story_id": "LABEL-001",
        "target_story_id": "",
        "stage": "regime_model_research",
    },
    "label_program_follow_on": {
        "story_class": "label_program",
        "source_story_id": "LABEL-001",
        "target_story_id": "STRAT-001",
        "stage": "regime_and_label_truth",
    },
    "strategy_eval_follow_on": {
        "story_class": "strategy_eval",
        "source_story_id": "STRAT-001",
        "target_story_id": "",
        "stage": "strategy_research",
    },
    "paper_cycle_follow_on": {
        "story_class": "paper_cycle",
        "source_story_id": "",
        "target_story_id": "",
        "stage": "paper_runtime",
    },
}


def _loads_json(text: str | None, default: Any) -> Any:
    if not text:
        return default
    try:
        return orjson.loads(text)
    except orjson.JSONDecodeError:
        return default


class ProposalReviewer:
    """Review bounded proposals without granting runtime authority."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def review_proposal(self, proposal_id: str) -> dict[str, Any]:
        session = get_session(self.settings)
        review_time = utcnow()
        try:
            proposal = (
                session.query(ImprovementProposalV1)
                .filter_by(proposal_id=proposal_id)
                .one_or_none()
            )
            if proposal is None:
                raise RuntimeError(f"Unknown proposal_id: {proposal_id}")

            source_artifacts = (
                session.query(ArtifactReference)
                .filter_by(
                    owner_type=proposal.source_owner_type,
                    owner_key=proposal.source_owner_key,
                )
                .order_by(ArtifactReference.created_at.asc(), ArtifactReference.id.asc())
                .all()
            )
            proposal_metrics = _loads_json(proposal.metrics_json, {})
            proposal_reason_codes = list(_loads_json(proposal.reason_codes_json, []))
            source_context = self._build_source_context(session, proposal, source_artifacts)
            decision_payload = self._build_decision(
                proposal=proposal,
                proposal_metrics=proposal_metrics,
                proposal_reason_codes=proposal_reason_codes,
                source_context=source_context,
            )

            review_id = f"review_{proposal.proposal_kind}_{uuid.uuid4().hex[:12]}"
            review_row = ProposalReviewV1(
                review_id=review_id,
                proposal_id=proposal.proposal_id,
                decision=decision_payload["decision"],
                reviewer_kind="ai_reviewer",
                summary=decision_payload["summary"],
                reason_codes_json=orjson.dumps(decision_payload["reason_codes"]).decode(),
                regime_scope_json=orjson.dumps(decision_payload["regime_scope"]).decode(),
                condition_scope_json=orjson.dumps(
                    decision_payload["condition_scope"]
                ).decode(),
                recommended_next_test=decision_payload["recommended_next_test"],
                created_at=review_time,
            )
            session.add(review_row)
            previous_status = proposal.status
            proposal.status = decision_payload["decision"]
            session.commit()
        finally:
            session.close()

        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "proposal_reviews"
            / proposal_id
            / review_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        review_payload = {
            "review_id": review_id,
            "proposal_id": proposal_id,
            "proposal_kind": proposal.proposal_kind,
            "source_owner_type": proposal.source_owner_type,
            "source_owner_key": proposal.source_owner_key,
            "previous_status": previous_status,
            "decision": decision_payload["decision"],
            "reviewer_kind": "ai_reviewer",
            "summary": decision_payload["summary"],
            "reason_codes": decision_payload["reason_codes"],
            "regime_scope": decision_payload["regime_scope"],
            "condition_scope": decision_payload["condition_scope"],
            "recommended_next_test": decision_payload["recommended_next_test"],
            "proposal_metrics": proposal_metrics,
            "source_metrics": decision_payload["source_metrics"],
            "source_artifact_types": decision_payload["source_artifact_types"],
            "source_artifact_count": len(source_artifacts),
            "source_artifact_path": decision_payload["source_artifact_path"],
            "story_class": decision_payload["story_class"],
            "source_story_id": decision_payload["source_story_id"],
            "target_story_id": decision_payload["target_story_id"],
            "stage": decision_payload["stage"],
            "reviewed_at": review_time.isoformat(),
        }
        write_json_artifact(
            artifact_dir / "review.json",
            review_payload,
            owner_type="proposal_review",
            owner_key=review_id,
            artifact_type="proposal_review",
            settings=self.settings,
            metadata={"proposal_id": proposal_id},
        )
        write_text_artifact(
            artifact_dir / "review.qmd",
            render_qmd(
                "proposal_review.qmd",
                title=f"Proposal review: {proposal.title}",
                summary_lines=[
                    f"- proposal id: `{proposal_id}`",
                    f"- review id: `{review_id}`",
                    f"- decision: `{decision_payload['decision']}`",
                    f"- source owner: `{proposal.source_owner_type}:{proposal.source_owner_key}`",
                    f"- governance scope: `{proposal.governance_scope}`",
                ],
                sections=[
                    ("Summary", [decision_payload["summary"]]),
                    (
                        "Reason Codes",
                        [
                            f"- `{item}`"
                            for item in decision_payload["reason_codes"]
                        ]
                        or ["- none recorded"],
                    ),
                    (
                        "Regime Scope",
                        [
                            f"- `{key}`: `{value}`"
                            for key, value in sorted(
                                decision_payload["regime_scope"].items()
                            )
                        ]
                        or ["- no regime context available"],
                    ),
                    (
                        "Condition Scope",
                        [
                            f"- `{key}`: `{value}`"
                            for key, value in sorted(
                                decision_payload["condition_scope"].items()
                            )
                        ]
                        or ["- no condition context available"],
                    ),
                    (
                        "Source Metrics",
                        [
                            f"- `{key}`: `{value}`"
                            for key, value in sorted(
                                decision_payload["source_metrics"].items()
                            )
                        ]
                        or ["- no source metrics recorded"],
                    ),
                    ("Recommended Next Test", [decision_payload["recommended_next_test"]]),
                ],
                generated_at=review_time,
            ),
            owner_type="proposal_review",
            owner_key=review_id,
            artifact_type="proposal_review_qmd",
            artifact_format="qmd",
            settings=self.settings,
            metadata={"proposal_id": proposal_id},
        )

        receipt_payload = {
            "receipt_id": f"proposal_review::{proposal_id}::{review_time.strftime('%Y%m%dT%H%M%SZ')}",
            "review_id": review_id,
            "proposal_id": proposal_id,
            "source_story_id": decision_payload["source_story_id"],
            "target_story_id": decision_payload["target_story_id"],
            "source_artifact_path": decision_payload["source_artifact_path"] or "",
            "status": decision_payload["decision"],
            "summary": decision_payload["summary"],
            "story_class": decision_payload["story_class"],
            "stage": decision_payload["stage"],
            "metrics": decision_payload["source_metrics"],
            "updated_at": review_time.isoformat(),
        }
        receipt_path = (
            self.settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "research_proposal_review_receipt.json"
        )
        write_json_artifact(
            receipt_path,
            receipt_payload,
            owner_type="proposal_review",
            owner_key=review_id,
            artifact_type="research_proposal_review_receipt",
            settings=self.settings,
            metadata={"proposal_id": proposal_id},
        )

        return {
            "proposal_id": proposal_id,
            "review_id": review_id,
            "decision": decision_payload["decision"],
            "artifact_dir": str(artifact_dir),
            "receipt_path": str(receipt_path),
            "summary": decision_payload["summary"],
            "source_story_id": decision_payload["source_story_id"],
            "target_story_id": decision_payload["target_story_id"],
        }

    def _build_source_context(
        self,
        session,
        proposal: ImprovementProposalV1,
        source_artifacts: list[ArtifactReference],
    ) -> dict[str, Any]:
        primary_artifact_payload = self._load_primary_artifact_payload(source_artifacts)
        hint_payload = _PROPOSAL_KIND_HINTS.get(proposal.proposal_kind, {})
        condition_snapshot, condition_source = self._resolve_condition_snapshot(
            session,
            proposal=proposal,
        )
        policy_trace, risk_gate = self._resolve_policy_risk_evidence(
            session,
            proposal=proposal,
        )
        source_metrics: dict[str, float] = {}
        source_status = ""
        if proposal.source_owner_type == "experiment_run":
            run = (
                session.query(ExperimentRun)
                .filter_by(run_id=proposal.source_owner_key)
                .one_or_none()
            )
            source_status = str(run.status) if run is not None else ""
            metric_rows = (
                session.query(ExperimentMetric)
                .filter_by(experiment_run_id=proposal.source_owner_key)
                .all()
            )
            source_metrics = {
                metric.metric_name: metric.metric_value
                for metric in metric_rows
                if metric.metric_value is not None
            }
        elif proposal.source_owner_type == "paper_session":
            paper_session = (
                session.query(PaperSession)
                .filter_by(session_key=proposal.source_owner_key)
                .one_or_none()
            )
            source_status = str(paper_session.status) if paper_session is not None else ""
            if paper_session is not None:
                paper_report = (
                    session.query(PaperSessionReport)
                    .filter_by(session_id=paper_session.id)
                    .order_by(desc(PaperSessionReport.created_at), desc(PaperSessionReport.id))
                    .first()
                )
                latest_fill = (
                    session.query(PaperFill)
                    .filter_by(session_id=paper_session.id)
                    .order_by(desc(PaperFill.created_at), desc(PaperFill.id))
                    .first()
                )
                if paper_report is not None:
                    source_metrics.update(
                        {
                            "paper_equity_usdc": paper_report.equity_usdc,
                            "paper_cash_usdc": paper_report.cash_usdc,
                            "paper_position_value_usdc": paper_report.position_value_usdc,
                            "paper_realized_pnl_usdc": paper_report.realized_pnl_usdc,
                            "paper_unrealized_pnl_usdc": paper_report.unrealized_pnl_usdc,
                        }
                    )
                if latest_fill is not None:
                    source_metrics.update(
                        {
                            "paper_fill_price_usdc": latest_fill.fill_price_usdc,
                            "paper_fill_slippage_bps": float(latest_fill.slippage_bps or 0),
                            "paper_fill_price_impact_pct": float(
                                latest_fill.price_impact_pct or 0.0
                            ),
                        }
                    )

        regime_scope = {
            "source": condition_source,
            "semantic_regime": getattr(condition_snapshot, "semantic_regime", None),
            "confidence": getattr(condition_snapshot, "confidence", None),
            "macro_context_state": getattr(condition_snapshot, "macro_context_state", None),
            "blocked_flag": getattr(condition_snapshot, "blocked_flag", None),
        }
        condition_scope = {
            "condition_run_id": getattr(condition_snapshot, "condition_run_id", None),
            "bucket_start_utc": (
                condition_snapshot.bucket_start_utc.isoformat()
                if getattr(condition_snapshot, "bucket_start_utc", None) is not None
                else None
            ),
            "policy_state": getattr(policy_trace, "policy_state", None),
            "risk_state": getattr(risk_gate, "risk_state", None),
            "condition_blocked_flag": getattr(risk_gate, "condition_blocked_flag", None),
            "stale_data_authorized_flag": getattr(
                risk_gate, "stale_data_authorized_flag", None
            ),
            "unresolved_input_flag": getattr(
                risk_gate, "unresolved_input_flag", None
            ),
        }
        return {
            "source_metrics": source_metrics,
            "source_status": source_status,
            "source_artifact_payload": primary_artifact_payload,
            "source_artifact_types": sorted(
                {artifact.artifact_type for artifact in source_artifacts}
            ),
            "source_artifact_path": primary_artifact_payload["artifact_path"],
            "story_class": primary_artifact_payload["story_class"]
            or str(hint_payload.get("story_class") or ""),
            "source_story_id": primary_artifact_payload["source_story_id"]
            or str(hint_payload.get("source_story_id") or ""),
            "target_story_id": primary_artifact_payload["target_story_id"]
            or str(hint_payload.get("target_story_id") or ""),
            "stage": primary_artifact_payload["stage"]
            or str(hint_payload.get("stage") or ""),
            "regime_scope": regime_scope,
            "condition_scope": condition_scope,
        }

    def _build_decision(
        self,
        *,
        proposal: ImprovementProposalV1,
        proposal_metrics: dict[str, Any],
        proposal_reason_codes: list[str],
        source_context: dict[str, Any],
    ) -> dict[str, Any]:
        reject_codes: list[str] = []
        hold_codes: list[str] = []

        if proposal.runtime_effect != "advisory_only":
            reject_codes.append("runtime_effect_not_advisory_only")
        if proposal.governance_scope not in _SUPPORTED_GOVERNANCE_SCOPES:
            reject_codes.append("unsupported_governance_scope")
        if self._contains_unsafe_runtime_language(proposal):
            reject_codes.append("unsafe_runtime_widening_language")
        if proposal.source_owner_type not in {"experiment_run", "paper_session"}:
            reject_codes.append("unsupported_source_owner_type")

        if not source_context["source_artifact_types"]:
            hold_codes.append("missing_source_artifacts")
        if not proposal_metrics:
            hold_codes.append("missing_proposal_metrics")
        if not source_context["source_metrics"]:
            hold_codes.append("missing_source_metrics")
        if (
            proposal.source_owner_type == "experiment_run"
            and source_context["source_status"] != "success"
            and source_context["source_status"]
        ):
            hold_codes.append("source_run_not_success")
        if source_context["regime_scope"].get("semantic_regime") in {None, ""}:
            hold_codes.append("missing_regime_context")
        if source_context["condition_scope"].get("condition_run_id") in {None, ""}:
            hold_codes.append("missing_condition_context")

        reason_codes = [*proposal_reason_codes]
        reason_codes.extend(code for code in reject_codes if code not in reason_codes)
        decision = "reviewed_accept"
        summary = (
            "Evidence is complete, advisory-only, and bounded to the current "
            "regime/condition context."
        )
        if reject_codes:
            decision = "reviewed_reject"
            summary = (
                "Rejected because the proposal implies runtime or governance widening "
                "outside the bounded advisory review surface."
            )
        elif hold_codes:
            decision = "reviewed_hold"
            summary = (
                "Held because the proposal packet is still missing enough evidence to "
                "support a bounded next experiment under the current regime/condition "
                "view."
            )

        for code in hold_codes:
            if code not in reason_codes:
                reason_codes.append(code)
        if decision == "reviewed_accept":
            for code in ("evidence_verified", "advisory_scope_preserved"):
                if code not in reason_codes:
                    reason_codes.append(code)

        recommended_next_test = proposal.next_test
        if decision == "reviewed_hold":
            recommended_next_test = (
                "Refresh the missing evidence packet, then rerun `d5 review-proposal "
                f"{proposal.proposal_id}` without widening runtime authority."
            )
        elif decision == "reviewed_reject":
            recommended_next_test = (
                "Write a narrower advisory-only proposal that avoids live trading, "
                "wallet, or risk-widening language and stays inside the current "
                "governance scope."
            )

        return {
            "decision": decision,
            "summary": summary,
            "reason_codes": reason_codes,
            "regime_scope": source_context["regime_scope"],
            "condition_scope": source_context["condition_scope"],
            "recommended_next_test": recommended_next_test,
            "source_metrics": source_context["source_metrics"],
            "source_artifact_types": source_context["source_artifact_types"],
            "source_artifact_path": source_context["source_artifact_path"],
            "story_class": source_context["story_class"],
            "source_story_id": source_context["source_story_id"],
            "target_story_id": source_context["target_story_id"],
            "stage": source_context["stage"],
        }

    def _load_primary_artifact_payload(
        self,
        source_artifacts: list[ArtifactReference],
    ) -> dict[str, Any]:
        hints = {
            "artifact_path": "",
            "story_class": "",
            "source_story_id": "",
            "target_story_id": "",
            "stage": "",
        }
        for artifact_type in _SOURCE_ARTIFACT_PRIORITY:
            for artifact in source_artifacts:
                if artifact.artifact_type != artifact_type or artifact.artifact_format != "json":
                    continue
                path = Path(artifact.artifact_path)
                if not path.exists():
                    continue
                payload = _loads_json(path.read_bytes().decode("utf-8"), {})
                hints.update(
                    {
                        "artifact_path": str(path),
                        "story_class": str(
                            _PROPOSAL_KIND_HINTS.get(
                                self._proposal_kind_from_artifact_type(artifact_type), {}
                            ).get("story_class", "")
                        ),
                        "source_story_id": str(payload.get("story_id") or ""),
                        "target_story_id": str(payload.get("next_story_id") or ""),
                        "stage": str(payload.get("stage") or ""),
                    }
                )
                return hints
        return hints

    def _proposal_kind_from_artifact_type(self, artifact_type: str) -> str:
        if artifact_type == "regime_model_compare_summary":
            return "regime_model_compare_follow_on"
        if artifact_type == "label_program_candidate":
            return "label_program_follow_on"
        if artifact_type == "strategy_challenger_report":
            return "strategy_eval_follow_on"
        if artifact_type == "paper_cycle_summary":
            return "paper_cycle_follow_on"
        return ""

    def _resolve_condition_snapshot(self, session, *, proposal: ImprovementProposalV1):
        if proposal.source_owner_type == "paper_session":
            paper_session = (
                session.query(PaperSession)
                .filter_by(session_key=proposal.source_owner_key)
                .one_or_none()
            )
            if paper_session is not None:
                latest_fill = (
                    session.query(PaperFill)
                    .filter_by(session_id=paper_session.id)
                    .order_by(desc(PaperFill.created_at), desc(PaperFill.id))
                    .first()
                )
                if latest_fill is not None:
                    snapshot = (
                        session.query(ConditionGlobalRegimeSnapshotV1)
                        .filter_by(id=latest_fill.condition_snapshot_id)
                        .one_or_none()
                    )
                    if snapshot is not None:
                        return snapshot, "paper_fill_attached_condition_snapshot"

        snapshot = (
            session.query(ConditionGlobalRegimeSnapshotV1)
            .order_by(
                desc(ConditionGlobalRegimeSnapshotV1.bucket_start_utc),
                desc(ConditionGlobalRegimeSnapshotV1.id),
            )
            .first()
        )
        return snapshot, "latest_condition_snapshot"

    def _resolve_policy_risk_evidence(self, session, *, proposal: ImprovementProposalV1):
        if proposal.source_owner_type == "paper_session":
            paper_session = (
                session.query(PaperSession)
                .filter_by(session_key=proposal.source_owner_key)
                .one_or_none()
            )
            if paper_session is not None:
                latest_fill = (
                    session.query(PaperFill)
                    .filter_by(session_id=paper_session.id)
                    .order_by(desc(PaperFill.created_at), desc(PaperFill.id))
                    .first()
                )
                if latest_fill is not None:
                    policy_trace = (
                        session.query(PolicyGlobalRegimeTraceV1)
                        .filter_by(id=latest_fill.policy_trace_id)
                        .one_or_none()
                    )
                    risk_gate = (
                        session.query(RiskGlobalRegimeGateV1)
                        .filter_by(id=latest_fill.risk_verdict_id)
                        .one_or_none()
                    )
                    return policy_trace, risk_gate

        policy_trace = (
            session.query(PolicyGlobalRegimeTraceV1)
            .order_by(
                desc(PolicyGlobalRegimeTraceV1.bucket_start_utc),
                desc(PolicyGlobalRegimeTraceV1.id),
            )
            .first()
        )
        risk_gate = (
            session.query(RiskGlobalRegimeGateV1)
            .order_by(
                desc(RiskGlobalRegimeGateV1.bucket_start_utc),
                desc(RiskGlobalRegimeGateV1.id),
            )
            .first()
        )
        return policy_trace, risk_gate

    def _contains_unsafe_runtime_language(self, proposal: ImprovementProposalV1) -> bool:
        haystack = " ".join(
            [
                proposal.title or "",
                proposal.summary or "",
                proposal.hypothesis or "",
                proposal.next_test or "",
            ]
        ).lower()
        return any(phrase in haystack for phrase in _UNSAFE_RUNTIME_PHRASES)
