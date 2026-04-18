from __future__ import annotations

import json
from pathlib import Path

from d5_trading_engine.cli import cli
from d5_trading_engine.research_loop.proposal_review import ProposalReviewer
from d5_trading_engine.research_loop.regime_model_compare import (
    RegimeModelComparator,
    _CandidateOutcome,
)
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ExperimentMetric,
    ExperimentRun,
    ImprovementProposalV1,
    ProposalReviewV1,
)
from tests.test_condition_scoring import _seed_global_regime_inputs


def _prepare_regime_compare_history(
    cli_runner,
    settings,
    *,
    total_15m_buckets: int = 96,
    score_conditions: bool = False,
) -> None:
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _seed_global_regime_inputs(settings, total_15m_buckets=total_15m_buckets)
    result = cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"])
    assert result.exit_code == 0
    if score_conditions:
        score_result = cli_runner.invoke(cli, ["score-conditions", "global-regime-v1"])
        assert score_result.exit_code == 0


def _candidate_runner(
    *,
    key: str,
    model_family: str,
    semantic_regime: str,
    mean_confidence: float,
    adjacent_flip_rate: float,
    log_likelihood: float | None = None,
):
    def _run(self, history, macro_context_state):
        del macro_context_state
        scored_rows = []
        for index, bucket_start_utc in enumerate(history["bucket_start_utc"].iloc[63:]):
            scored_rows.append(
                {
                    "bucket_start_utc": bucket_start_utc.isoformat(),
                    "raw_state_id": index % 4,
                    "confidence": float(mean_confidence),
                    "semantic_regime": semantic_regime,
                }
            )
        return _CandidateOutcome(
            key=key,
            model_family=model_family,
            available=True,
            fit_success=True,
            fit_seconds=0.031,
            prediction_rows=len(scored_rows),
            state_count=4,
            mean_confidence=float(mean_confidence),
            adjacent_flip_rate=float(adjacent_flip_rate),
            semantic_mapping_coverage=1.0,
            fail_closed=False,
            log_likelihood=log_likelihood,
            error=None,
            scored_history=scored_rows,
        )

    return _run


def test_cli_run_shadow_regime_model_compare_persists_receipts_and_artifacts(
    cli_runner,
    settings,
    monkeypatch,
) -> None:
    _prepare_regime_compare_history(cli_runner, settings)

    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_hmm_candidate",
        _candidate_runner(
            key="hmm",
            model_family="gaussian_hmm_4state",
            semantic_regime="long_friendly",
            mean_confidence=0.74,
            adjacent_flip_rate=0.22,
        ),
    )
    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_gmm_candidate",
        _candidate_runner(
            key="gmm",
            model_family="gaussian_mixture_4state",
            semantic_regime="no_trade",
            mean_confidence=0.69,
            adjacent_flip_rate=0.28,
        ),
    )
    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_statsmodels_candidate",
        _candidate_runner(
            key="statsmodels",
            model_family="statsmodels_markov_regression_4state",
            semantic_regime="long_friendly",
            mean_confidence=0.88,
            adjacent_flip_rate=0.08,
            log_likelihood=12.5,
        ),
    )

    result = cli_runner.invoke(cli, ["run-shadow", "regime-model-compare-v1"])

    assert result.exit_code == 0
    assert "regime_model_compare_v1" in result.output
    assert "recommended=statsmodels" in result.output

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).one()
        metrics = (
            session.query(ExperimentMetric)
            .filter_by(experiment_run_id=run.run_id)
            .all()
        )
        proposal = session.query(ImprovementProposalV1).one()
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="experiment_run", owner_key=run.run_id)
            .all()
        )
    finally:
        session.close()

    metric_names = {metric.metric_name for metric in metrics}
    assert run.experiment_name == "regime_model_compare_v1"
    assert run.status == "success"
    assert proposal.proposal_kind == "regime_model_compare_follow_on"
    assert proposal.status == "proposed"
    assert {
        "dataset_rows",
        "feature_bucket_rows",
        "massive_history_present",
        "hmm_available",
        "gmm_available",
        "statsmodels_available",
        "statsmodels_fit_success",
        "statsmodels_log_likelihood",
    } <= metric_names
    assert {artifact.artifact_type for artifact in artifacts} == {
        "regime_model_compare_config",
        "regime_model_compare_history_inventory",
        "regime_model_compare_report_qmd",
        "regime_model_compare_summary",
    }

    artifact_dir = settings.data_dir / "research" / "regime_model_compare" / run.run_id
    comparison_payload = json.loads((artifact_dir / "comparison.json").read_text(encoding="utf-8"))
    assert comparison_payload["status"] == "success"
    assert comparison_payload["recommendation"]["recommended_candidate"] == "statsmodels"
    assert comparison_payload["history_inventory"]["massive_history"]["present"] is False


def test_cli_run_shadow_regime_model_compare_handles_missing_statsmodels_dependency(
    cli_runner,
    settings,
    monkeypatch,
) -> None:
    _prepare_regime_compare_history(cli_runner, settings)

    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_hmm_candidate",
        _candidate_runner(
            key="hmm",
            model_family="gaussian_hmm_4state",
            semantic_regime="long_friendly",
            mean_confidence=0.73,
            adjacent_flip_rate=0.18,
        ),
    )
    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_gmm_candidate",
        _candidate_runner(
            key="gmm",
            model_family="gaussian_mixture_4state",
            semantic_regime="no_trade",
            mean_confidence=0.66,
            adjacent_flip_rate=0.31,
        ),
    )
    monkeypatch.setattr(
        "d5_trading_engine.research_loop.regime_model_compare.statsmodels_regime_available",
        lambda: False,
    )

    result = cli_runner.invoke(cli, ["run-shadow", "regime-model-compare-v1"])

    assert result.exit_code == 0

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).one()
        metrics = {
            row.metric_name: row.metric_value
            for row in session.query(ExperimentMetric)
            .filter_by(experiment_run_id=run.run_id)
            .all()
        }
    finally:
        session.close()

    comparison_payload = json.loads(
        (
            settings.data_dir
            / "research"
            / "regime_model_compare"
            / run.run_id
            / "comparison.json"
        ).read_text(encoding="utf-8")
    )

    assert metrics["statsmodels_available"] == 0.0
    assert metrics["statsmodels_fit_success"] == 0.0
    assert comparison_payload["candidates"]["statsmodels"]["available"] is False
    assert "optional statsmodels dependency missing" in (
        comparison_payload["candidates"]["statsmodels"]["error"] or ""
    )


def test_cli_run_shadow_regime_model_compare_fails_closed_on_short_history(
    cli_runner,
    settings,
) -> None:
    _prepare_regime_compare_history(cli_runner, settings, total_15m_buckets=72)

    result = cli_runner.invoke(cli, ["run-shadow", "regime-model-compare-v1"])

    assert result.exit_code != 0
    assert "Need at least 80 15-minute rows for regime comparison" in result.output

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).one()
        proposals = session.query(ImprovementProposalV1).all()
    finally:
        session.close()

    assert run.experiment_name == "regime_model_compare_v1"
    assert run.status == "failed"
    assert "Need at least 80 15-minute rows" in (run.conclusion or "")
    assert proposals == []

    comparison_payload = json.loads(
        (
            settings.data_dir
            / "research"
            / "regime_model_compare"
            / run.run_id
            / "comparison.json"
        ).read_text(encoding="utf-8")
    )
    assert comparison_payload["status"] == "failed"


def test_proposal_review_accepts_regime_model_compare_follow_on(
    cli_runner,
    settings,
    monkeypatch,
) -> None:
    _prepare_regime_compare_history(cli_runner, settings, score_conditions=True)

    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_hmm_candidate",
        _candidate_runner(
            key="hmm",
            model_family="gaussian_hmm_4state",
            semantic_regime="long_friendly",
            mean_confidence=0.72,
            adjacent_flip_rate=0.21,
        ),
    )
    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_gmm_candidate",
        _candidate_runner(
            key="gmm",
            model_family="gaussian_mixture_4state",
            semantic_regime="no_trade",
            mean_confidence=0.67,
            adjacent_flip_rate=0.29,
        ),
    )
    monkeypatch.setattr(
        RegimeModelComparator,
        "_run_statsmodels_candidate",
        _candidate_runner(
            key="statsmodels",
            model_family="statsmodels_markov_regression_4state",
            semantic_regime="long_friendly",
            mean_confidence=0.87,
            adjacent_flip_rate=0.09,
            log_likelihood=13.2,
        ),
    )

    compare_result = RegimeModelComparator(settings).run_regime_model_compare_v1()
    review_result = ProposalReviewer(settings).review_proposal(compare_result["proposal_id"])

    session = get_session(settings)
    try:
        proposal_row = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=compare_result["proposal_id"])
            .one()
        )
        review_row = (
            session.query(ProposalReviewV1)
            .filter_by(review_id=review_result["review_id"])
            .one()
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
        ).read_text(encoding="utf-8")
    )

    assert review_result["decision"] == "reviewed_accept"
    assert proposal_row.status == "reviewed_accept"
    assert review_row.decision == "reviewed_accept"
    assert receipt["proposal_id"] == compare_result["proposal_id"]
    assert receipt["story_class"] == "regime_model_compare"
    assert receipt["source_story_id"] == "LABEL-001"
