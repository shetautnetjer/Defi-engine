from __future__ import annotations

import json
from pathlib import Path

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.reporting.artifacts import write_json_artifact
from d5_trading_engine.reporting.proposals import create_improvement_proposal
from d5_trading_engine.research_loop.proposal_comparison import ProposalComparator
from d5_trading_engine.research_loop.proposal_review import ProposalReviewer
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    ExperimentMetric,
    ExperimentRun,
    FeatureMaterializationRun,
    ImprovementProposalV1,
    ProposalComparisonItemV1,
    ProposalComparisonV1,
    ProposalReviewV1,
    ProposalSupersessionV1,
)


def _seed_reviewable_experiment_context(settings, *, run_id: str) -> None:
    now = utcnow().replace(second=0, microsecond=0)
    feature_run_id = f"feature_{run_id}"
    condition_run_id = f"condition_{run_id}"

    session = get_session(settings)
    try:
        session.add(
            FeatureMaterializationRun(
                run_id=feature_run_id,
                feature_set="global_regime_inputs_15m_v1",
                source_tables="[]",
                freshness_snapshot_json="{}",
                input_window_start_utc=now,
                input_window_end_utc=now,
                row_count=1,
                status="success",
                started_at=now,
                finished_at=now,
                error_message=None,
                created_at=now,
            )
        )
        session.commit()

        session.add(
            ConditionScoringRun(
                run_id=condition_run_id,
                condition_set="global_regime_v1",
                source_feature_run_id=feature_run_id,
                model_family="hmm",
                training_window_start_utc=now,
                training_window_end_utc=now,
                scored_bucket_start_utc=now,
                state_semantics_json="{}",
                model_params_json="{}",
                status="success",
                confidence=0.82,
                error_message=None,
                started_at=now,
                finished_at=now,
                created_at=now,
            )
        )
        session.commit()

        session.add(
            ConditionGlobalRegimeSnapshotV1(
                condition_run_id=condition_run_id,
                source_feature_run_id=feature_run_id,
                bucket_start_utc=now,
                raw_state_id=1,
                semantic_regime="trend_up",
                confidence=0.82,
                blocked_flag=0,
                blocking_reason=None,
                model_family="hmm",
                macro_context_state="risk_on",
                created_at=now,
            )
        )
        session.add(
            ExperimentRun(
                run_id=run_id,
                experiment_name="label_program_v1",
                hypothesis="test reviewable proposal",
                config_json="{}",
                status="success",
                started_at=now,
                finished_at=now,
                conclusion="ok",
                created_at=now,
            )
        )
        session.commit()

        session.add(
            ExperimentMetric(
                experiment_run_id=run_id,
                metric_name="label_program_auto_promotion_eligible",
                metric_value=1.0,
                metric_metadata=None,
                recorded_at=now,
            )
        )
        session.commit()
    finally:
        session.close()

    write_json_artifact(
        settings.data_dir / "research" / "seed_review" / run_id / "label_program_candidate.json",
        {
            "artifact_type": "label_program_candidate",
            "run_id": run_id,
            "story_id": "LABEL-001",
            "stage": "regime_and_label_truth",
            "families": {"direction_60m_v1": {"eligible": True}},
            "auto_promotion_eligible": True,
            "next_story_id": "STRAT-001",
            "generated_at": now.isoformat(),
        },
        owner_type="experiment_run",
        owner_key=run_id,
        artifact_type="label_program_candidate",
        settings=settings,
    )


def _seed_strategy_experiment_context(settings, *, run_id: str) -> None:
    now = utcnow().replace(second=0, microsecond=0)
    session = get_session(settings)
    try:
        session.add(
            ExperimentRun(
                run_id=run_id,
                experiment_name="strategy_eval_v1",
                hypothesis="test reviewable strategy proposal",
                config_json="{}",
                status="success",
                started_at=now,
                finished_at=now,
                conclusion="ok",
                created_at=now,
            )
        )
        session.flush()
        session.add_all(
            [
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="trend_continuation_long_v1_positive_expectancy",
                    metric_value=0.08,
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="trend_continuation_long_v1_xgb_accuracy",
                    metric_value=0.71,
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="trend_continuation_long_v1_xgb_auc",
                    metric_value=0.74,
                    metric_metadata=None,
                    recorded_at=now,
                ),
            ]
        )
        session.commit()
    finally:
        session.close()

    write_json_artifact(
        settings.data_dir / "research" / "seed_review" / run_id / "strategy_challenger_report.json",
        {
            "artifact_type": "strategy_challenger_report",
            "run_id": run_id,
            "story_id": "STRAT-001",
            "stage": "strategy_research",
            "top_family": "trend_continuation_long_v1",
            "auto_promotion_eligible": True,
            "families": {
                "trend_continuation_long_v1": {
                    "eligible": True,
                    "positive_expectancy": 0.08,
                    "xgb_accuracy": 0.71,
                    "xgb_auc": 0.74,
                }
            },
        },
        owner_type="experiment_run",
        owner_key=run_id,
        artifact_type="strategy_challenger_report",
        settings=settings,
    )


def _mark_proposal_reviewed(
    settings,
    *,
    proposal_id: str,
    decision: str,
    semantic_regime: str = "trend_up",
    macro_context_state: str = "risk_on",
    condition_run_id: str = "condition_current",
) -> None:
    now = utcnow()
    session = get_session(settings)
    try:
        proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal_id)
            .one()
        )
        proposal.status = decision
        session.add(
            ProposalReviewV1(
                review_id=f"review_{proposal_id}",
                proposal_id=proposal_id,
                decision=decision,
                reviewer_kind="ai_reviewer",
                summary=f"{decision} seeded for comparison testing",
                reason_codes_json=json.dumps(["seeded_review"]),
                regime_scope_json=json.dumps(
                    {
                        "semantic_regime": semantic_regime,
                        "macro_context_state": macro_context_state,
                    }
                ),
                condition_scope_json=json.dumps(
                    {
                        "condition_run_id": condition_run_id,
                    }
                ),
                recommended_next_test="Run the bounded next comparison step.",
                created_at=now,
            )
        )
        session.commit()
    finally:
        session.close()


def test_improvement_proposal_writes_truth_and_evidence(settings) -> None:
    run_migrations_to_head(settings)
    artifact_dir = settings.data_dir / "research" / "proposal_test"

    proposal = create_improvement_proposal(
        artifact_dir=artifact_dir,
        proposal_kind="strategy_eval_followup",
        source_owner_type="experiment_run",
        source_owner_key="experiment_001",
        governance_scope="research_only",
        title="Test proposal",
        summary="Compare the current governed challenger against a tighter regime slice.",
        hypothesis="Restricting to long_friendly buckets will improve expectancy stability.",
        next_test="Run governed_challengers_v1 with a long_friendly-only cohort.",
        metrics={"positive_expectancy": 0.0, "rows_test": 16},
        reason_codes=["needs_more_history", "proposal_only"],
        settings=settings,
    )

    session = get_session(settings)
    try:
        row = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal["proposal_id"])
            .one()
        )
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="proposal", owner_key=proposal["proposal_id"])
            .all()
        )
    finally:
        session.close()

    assert row.status == "proposed"
    assert row.runtime_effect == "advisory_only"
    assert (artifact_dir / "proposal.json").exists()
    assert (artifact_dir / "proposal.qmd").exists()
    assert {artifact.artifact_type for artifact in artifacts} == {
        "improvement_proposal",
        "improvement_proposal_qmd",
    }


def test_proposal_review_writes_truth_receipts_and_accepts_bounded_evidence(settings) -> None:
    run_migrations_to_head(settings)
    run_id = "experiment_reviewable_001"
    _seed_reviewable_experiment_context(settings, run_id=run_id)
    artifact_dir = settings.data_dir / "research" / "proposal_review_accept_test"

    proposal = create_improvement_proposal(
        artifact_dir=artifact_dir,
        proposal_kind="label_program_follow_on",
        source_owner_type="experiment_run",
        source_owner_key=run_id,
        governance_scope="research_loop",
        title="Review bounded label evidence",
        summary="The label packet is ready for a bounded next-step review.",
        hypothesis="A bounded review should accept evidence that stays advisory-only.",
        next_test="Review the best label family and run governed strategy evaluation.",
        metrics={"eligible_family_count": 1, "dropbox_artifact_written": 1.0},
        reason_codes=["operator_review_required", "proposal_only_follow_on"],
        settings=settings,
    )

    result = ProposalReviewer(settings).review_proposal(proposal["proposal_id"])

    session = get_session(settings)
    try:
        proposal_row = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal["proposal_id"])
            .one()
        )
        review_row = (
            session.query(ProposalReviewV1)
            .filter_by(review_id=result["review_id"])
            .one()
        )
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="proposal_review", owner_key=result["review_id"])
            .all()
        )
    finally:
        session.close()

    receipt = json.loads(
        (
            settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "research_proposal_review_receipt.json"
        ).read_text()
    )

    assert result["decision"] == "reviewed_accept"
    assert proposal_row.status == "reviewed_accept"
    assert review_row.decision == "reviewed_accept"
    assert (Path(result["artifact_dir"]) / "review.json").exists()
    assert (Path(result["artifact_dir"]) / "review.qmd").exists()
    assert {artifact.artifact_type for artifact in artifacts} == {
        "proposal_review",
        "proposal_review_qmd",
        "research_proposal_review_receipt",
    }
    assert receipt["proposal_id"] == proposal["proposal_id"]
    assert receipt["story_class"] == "label_program"
    assert receipt["source_story_id"] == "LABEL-001"
    assert receipt["target_story_id"] == "STRAT-001"
    assert receipt["status"] == "reviewed_accept"


def test_proposal_review_rejects_runtime_widening_language(settings) -> None:
    run_migrations_to_head(settings)
    run_id = "experiment_reviewable_reject_001"
    _seed_reviewable_experiment_context(settings, run_id=run_id)
    artifact_dir = settings.data_dir / "research" / "proposal_review_reject_test"

    proposal = create_improvement_proposal(
        artifact_dir=artifact_dir,
        proposal_kind="label_program_follow_on",
        source_owner_type="experiment_run",
        source_owner_key=run_id,
        governance_scope="research_loop",
        title="Unsafe live widening proposal",
        summary="This proposal intentionally includes unsafe language for the safety test.",
        hypothesis="Unsafe language must force a bounded reject.",
        next_test="Enable live trading and disable risk checks for the next run.",
        metrics={"eligible_family_count": 1},
        reason_codes=["operator_review_required"],
        settings=settings,
    )

    result = ProposalReviewer(settings).review_proposal(proposal["proposal_id"])

    session = get_session(settings)
    try:
        proposal_row = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal["proposal_id"])
            .one()
        )
        review_row = (
            session.query(ProposalReviewV1)
            .filter_by(review_id=result["review_id"])
            .one()
        )
    finally:
        session.close()

    assert result["decision"] == "reviewed_reject"
    assert proposal_row.status == "reviewed_reject"
    assert review_row.decision == "reviewed_reject"
    assert "unsafe_runtime_widening_language" in json.loads(review_row.reason_codes_json)


def test_compare_proposals_choose_top_supersedes_same_kind_only(settings) -> None:
    run_migrations_to_head(settings)
    _seed_reviewable_experiment_context(settings, run_id="experiment_label_a")
    _seed_reviewable_experiment_context(settings, run_id="experiment_label_b")

    proposal_a = create_improvement_proposal(
        artifact_dir=settings.data_dir / "research" / "compare_label_a",
        proposal_kind="label_program_follow_on",
        source_owner_type="experiment_run",
        source_owner_key="experiment_label_a",
        governance_scope="research_loop",
        title="Label proposal A",
        summary="Compare label family A.",
        hypothesis="A stronger valid coverage should win.",
        next_test="Review family A.",
        metrics={"eligible_family_count": 1},
        reason_codes=["seeded"],
        settings=settings,
    )
    proposal_b = create_improvement_proposal(
        artifact_dir=settings.data_dir / "research" / "compare_label_b",
        proposal_kind="label_program_follow_on",
        source_owner_type="experiment_run",
        source_owner_key="experiment_label_b",
        governance_scope="research_loop",
        title="Label proposal B",
        summary="Compare label family B.",
        hypothesis="A weaker valid coverage should lose.",
        next_test="Review family B.",
        metrics={"eligible_family_count": 1},
        reason_codes=["seeded"],
        settings=settings,
    )

    for run_id, coverage in (
        ("experiment_label_a", 0.81),
        ("experiment_label_b", 0.62),
    ):
        session = get_session(settings)
        try:
            session.add_all(
                [
                    ExperimentMetric(
                        experiment_run_id=run_id,
                        metric_name="direction_60m_v1_valid_coverage",
                        metric_value=coverage,
                        metric_metadata=None,
                        recorded_at=utcnow(),
                    ),
                    ExperimentMetric(
                        experiment_run_id=run_id,
                        metric_name="direction_60m_v1_invalid_rate",
                        metric_value=0.08,
                        metric_metadata=None,
                        recorded_at=utcnow(),
                    ),
                    ExperimentMetric(
                        experiment_run_id=run_id,
                        metric_name="direction_60m_v1_low_confidence_rate",
                        metric_value=0.12,
                        metric_metadata=None,
                        recorded_at=utcnow(),
                    ),
                ]
            )
            session.commit()
        finally:
            session.close()

    _mark_proposal_reviewed(settings, proposal_id=proposal_a["proposal_id"], decision="reviewed_accept")
    _mark_proposal_reviewed(settings, proposal_id=proposal_b["proposal_id"], decision="reviewed_accept")

    result = ProposalComparator(settings).compare_proposals(
        proposal_ids=[proposal_a["proposal_id"], proposal_b["proposal_id"]],
        choose_top=True,
    )

    session = get_session(settings)
    try:
        selected = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal_a["proposal_id"])
            .one()
        )
        superseded = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal_b["proposal_id"])
            .one()
        )
        comparison = (
            session.query(ProposalComparisonV1)
            .filter_by(comparison_id=result["comparison_id"])
            .one()
        )
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="proposal_comparison", owner_key=result["comparison_id"])
            .all()
        )
        items = (
            session.query(ProposalComparisonItemV1)
            .filter_by(comparison_id=result["comparison_id"])
            .all()
        )
        supersession = session.query(ProposalSupersessionV1).one()
    finally:
        session.close()

    receipt = json.loads(
        (
            settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "research_proposal_priority_receipt.json"
        ).read_text(encoding="utf-8")
    )

    assert comparison.selection_mode == "choose_top"
    assert result["selected_proposal_id"] == proposal_a["proposal_id"]
    assert selected.status == "selected_next"
    assert superseded.status == "superseded"
    assert len(items) == 2
    assert {artifact.artifact_type for artifact in artifacts} == {
        "proposal_comparison",
        "proposal_comparison_qmd",
        "research_proposal_priority_receipt",
    }
    assert supersession.selected_proposal_id == proposal_a["proposal_id"]
    assert supersession.superseded_proposal_id == proposal_b["proposal_id"]
    assert receipt["selected_proposal_id"] == proposal_a["proposal_id"]
    assert receipt["superseded_proposal_ids"] == [proposal_b["proposal_id"]]


def test_compare_proposals_prefers_paper_over_earlier_stage_evidence(settings) -> None:
    run_migrations_to_head(settings)
    _seed_reviewable_experiment_context(settings, run_id="experiment_label_rank")
    _seed_strategy_experiment_context(settings, run_id="experiment_strategy_rank")

    label_proposal = create_improvement_proposal(
        artifact_dir=settings.data_dir / "research" / "compare_label_rank",
        proposal_kind="label_program_follow_on",
        source_owner_type="experiment_run",
        source_owner_key="experiment_label_rank",
        governance_scope="research_loop",
        title="Label ranking proposal",
        summary="Label evidence.",
        hypothesis="Label stage should rank below paper stage.",
        next_test="Run label follow-on.",
        metrics={"eligible_family_count": 1},
        reason_codes=["seeded"],
        settings=settings,
    )
    strategy_proposal = create_improvement_proposal(
        artifact_dir=settings.data_dir / "research" / "compare_strategy_rank",
        proposal_kind="strategy_eval_follow_on",
        source_owner_type="experiment_run",
        source_owner_key="experiment_strategy_rank",
        governance_scope="research_loop",
        title="Strategy ranking proposal",
        summary="Strategy evidence.",
        hypothesis="Strategy stage should rank below paper stage.",
        next_test="Run strategy follow-on.",
        metrics={"top_family_present": 1.0},
        reason_codes=["seeded"],
        settings=settings,
    )
    paper_proposal = create_improvement_proposal(
        artifact_dir=settings.data_dir / "research" / "compare_paper_rank",
        proposal_kind="paper_cycle_follow_on",
        source_owner_type="paper_session",
        source_owner_key="paper_session_rank",
        governance_scope="paper_runtime",
        title="Paper ranking proposal",
        summary="Paper evidence.",
        hypothesis="Paper evidence should outrank earlier-stage evidence.",
        next_test="Run the next bounded paper cycle.",
        metrics={"filled": 1.0, "regime_aligned": 1.0, "equity_usdc": 115.0},
        reason_codes=["seeded"],
        settings=settings,
    )

    _mark_proposal_reviewed(settings, proposal_id=label_proposal["proposal_id"], decision="reviewed_accept")
    _mark_proposal_reviewed(settings, proposal_id=strategy_proposal["proposal_id"], decision="reviewed_accept")
    _mark_proposal_reviewed(settings, proposal_id=paper_proposal["proposal_id"], decision="reviewed_accept")

    result = ProposalComparator(settings).compare_proposals(
        proposal_ids=[
            label_proposal["proposal_id"],
            strategy_proposal["proposal_id"],
            paper_proposal["proposal_id"],
        ],
        choose_top=True,
    )

    comparison_payload = json.loads(
        (
            Path(result["artifact_dir"]) / "comparison.json"
        ).read_text(encoding="utf-8")
    )

    assert result["selected_proposal_id"] == paper_proposal["proposal_id"]
    assert comparison_payload["ranked_items"][0]["proposal_id"] == paper_proposal["proposal_id"]
    assert comparison_payload["ranked_items"][1]["proposal_id"] == strategy_proposal["proposal_id"]
    assert comparison_payload["ranked_items"][2]["proposal_id"] == label_proposal["proposal_id"]
