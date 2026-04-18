from __future__ import annotations

import json
import shutil
from pathlib import Path

from d5_trading_engine.cli import cli
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ExperimentMetric,
    ExperimentRun,
    ImprovementProposalV1,
    ProposalReviewV1,
)
from tests.conftest import REPO_ROOT
from tests.test_shadow_runner import _prepare_shadow_runtime


def _seed_research_repo_truth(repo_root: Path) -> None:
    swarm_dir = repo_root / ".ai" / "swarm"
    swarm_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "story_classes.yaml",
        "metrics_registry.yaml",
        "strategy_registry.yaml",
        "instrument_scope.yaml",
    ):
        shutil.copy2(REPO_ROOT / ".ai" / "swarm" / name, swarm_dir / name)

    (repo_root / ".ai" / "dropbox" / "state").mkdir(parents=True, exist_ok=True)
    (repo_root / ".ai" / "dropbox" / "research").mkdir(parents=True, exist_ok=True)
    (repo_root / "progress.txt").write_text("", encoding="utf-8")
    (repo_root / "prd.json").write_text(
        json.dumps(
            {
                "project": "Defi-engine",
                "branchName": "main",
                "description": "test prd",
                "activeStoryId": "LABEL-001",
                "swarmState": "active",
                "completionAuditState": "pending",
                "lastCompletionAuditReceiptId": "",
                "lastFinderAuditId": "",
                "userStories": [
                    {
                        "id": "LABEL-001",
                        "title": "Canonical label program",
                        "state": "active",
                        "passes": False,
                        "recovery_round": 0,
                        "origin": "seeded",
                        "promoted_by": "",
                        "stage": "regime_and_label_truth",
                        "ownerLayer": "condition",
                        "derivedFrom": ["seeded"],
                        "whyNow": "Test proposal review.",
                        "mustNotWiden": "stay research-only",
                        "northStarLink": "docs/issues/governed_product_descent_capability_ladder.md#stage-3-regime-and-label-truth",
                    },
                    {
                        "id": "STRAT-001",
                        "title": "Strategy evaluation",
                        "state": "deferred",
                        "passes": False,
                        "recovery_round": 0,
                        "origin": "seeded",
                        "promoted_by": "",
                        "stage": "strategy_research",
                        "ownerLayer": "research_loop",
                        "derivedFrom": ["seeded"],
                        "whyNow": "Test advisory follow-on target.",
                        "mustNotWiden": "stay research-only",
                        "northStarLink": "docs/issues/governed_product_descent_capability_ladder.md#stage-4-strategy-research-layer",
                    },
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_cli_run_label_program_scores_and_records_proposal(cli_runner, settings) -> None:
    _seed_research_repo_truth(settings.repo_root)
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _prepare_shadow_runtime(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"]).exit_code == 0

    result = cli_runner.invoke(cli, ["run-label-program", "canonical-direction-v1"])
    assert result.exit_code == 0
    assert "canonical_direction_v1" in result.output
    assert "proposal=proposed" in result.output

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).filter_by(experiment_name="label_program_v1").one()
        metrics = (
            session.query(ExperimentMetric)
            .filter_by(experiment_run_id=run.run_id)
            .all()
        )
        proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(source_owner_type="experiment_run", source_owner_key=run.run_id)
            .one()
        )
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="experiment_run", owner_key=run.run_id)
            .all()
        )
    finally:
        session.close()

    artifact_dir = settings.data_dir / "research" / "label_program_runs" / run.run_id
    assert artifact_dir.exists()
    assert (artifact_dir / "config.json").exists()
    assert (artifact_dir / "label_program_candidate.json").exists()
    assert (artifact_dir / "dataset_preview.json").exists()
    assert (artifact_dir / "report.qmd").exists()
    assert (artifact_dir / "proposal.json").exists()
    assert (artifact_dir / "proposal.qmd").exists()
    assert any(metric.metric_name == "label_program_auto_promotion_eligible" for metric in metrics)
    assert any(metric.metric_name.endswith("_valid_coverage") for metric in metrics)
    assert proposal.status == "proposed"
    assert proposal.runtime_effect == "advisory_only"
    assert len(artifacts) >= 4

    candidate_report = json.loads((artifact_dir / "label_program_candidate.json").read_text())
    assert candidate_report["artifact_type"] == "label_program_candidate"
    assert "direction_60m_v1" in candidate_report["families"]

    dropbox_candidate = json.loads(
        (settings.repo_root / ".ai" / "dropbox" / "research" / "LABEL-001__label_program_candidate.json").read_text()
    )
    assert dropbox_candidate["artifact_type"] == "label_program_candidate"

    prd = json.loads((settings.repo_root / "prd.json").read_text())
    by_id = {story["id"]: story for story in prd["userStories"]}
    assert prd["activeStoryId"] == "LABEL-001"
    assert by_id["LABEL-001"]["state"] == "active"
    assert by_id["STRAT-001"]["state"] == "deferred"


def test_cli_run_strategy_eval_writes_challenger_report(cli_runner, settings) -> None:
    _seed_research_repo_truth(settings.repo_root)
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _prepare_shadow_runtime(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"]).exit_code == 0

    result = cli_runner.invoke(cli, ["run-strategy-eval", "governed-challengers-v1"])
    assert result.exit_code == 0
    assert "governed_challengers_v1" in result.output

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).filter_by(experiment_name="strategy_eval_v1").one()
        metrics = (
            session.query(ExperimentMetric)
            .filter_by(experiment_run_id=run.run_id)
            .all()
        )
        proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(source_owner_type="experiment_run", source_owner_key=run.run_id)
            .one()
        )
    finally:
        session.close()

    artifact_dir = settings.data_dir / "research" / "strategy_eval_runs" / run.run_id
    assert artifact_dir.exists()
    assert (artifact_dir / "config.json").exists()
    assert (artifact_dir / "strategy_challenger_report.json").exists()
    assert (artifact_dir / "dataset_preview.json").exists()
    assert (artifact_dir / "report.qmd").exists()
    assert (artifact_dir / "proposal.json").exists()
    assert (artifact_dir / "proposal.qmd").exists()
    assert any(metric.metric_name.endswith("_xgb_accuracy") for metric in metrics)
    assert any(metric.metric_name.endswith("_positive_expectancy") for metric in metrics)
    assert proposal.status == "proposed"
    assert proposal.runtime_effect == "advisory_only"

    challenger_report = json.loads((artifact_dir / "strategy_challenger_report.json").read_text())
    assert challenger_report["artifact_type"] == "strategy_challenger_report"
    assert set(challenger_report["families"]) <= {
        "trend_continuation_long_v1",
        "trend_continuation_short_v1",
        "flat_regime_stand_aside_v1",
    }

    dropbox_report = json.loads(
        (settings.repo_root / ".ai" / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json").read_text()
    )
    assert dropbox_report["artifact_type"] == "strategy_challenger_report"
    assert "artifact_path" in dropbox_report


def test_cli_review_proposal_records_acceptance_receipts(cli_runner, settings) -> None:
    _seed_research_repo_truth(settings.repo_root)
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _prepare_shadow_runtime(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"]).exit_code == 0
    assert cli_runner.invoke(cli, ["score-conditions", "global-regime-v1"]).exit_code == 0

    label_result = cli_runner.invoke(cli, ["run-label-program", "canonical-direction-v1"])
    assert label_result.exit_code == 0

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).filter_by(experiment_name="label_program_v1").one()
        proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(source_owner_type="experiment_run", source_owner_key=run.run_id)
            .one()
        )
    finally:
        session.close()

    result = cli_runner.invoke(cli, ["review-proposal", proposal.proposal_id])
    assert result.exit_code == 0
    assert "decision=reviewed_accept" in result.output

    session = get_session(settings)
    try:
        refreshed_proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(proposal_id=proposal.proposal_id)
            .one()
        )
        review = (
            session.query(ProposalReviewV1)
            .filter_by(proposal_id=proposal.proposal_id)
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
        ).read_text()
    )

    assert refreshed_proposal.status == "reviewed_accept"
    assert review.decision == "reviewed_accept"
    assert receipt["proposal_id"] == proposal.proposal_id
    assert receipt["story_class"] == "label_program"
    assert receipt["status"] == "reviewed_accept"


def test_cli_compare_proposals_selects_reviewed_candidate(cli_runner, settings) -> None:
    _seed_research_repo_truth(settings.repo_root)
    assert cli_runner.invoke(cli, ["init"]).exit_code == 0
    _prepare_shadow_runtime(settings)
    assert (
        cli_runner.invoke(cli, ["materialize-features", "global-regime-inputs-15m-v1"]).exit_code
        == 0
    )
    assert cli_runner.invoke(cli, ["materialize-features", "spot-chain-macro-v1"]).exit_code == 0
    assert cli_runner.invoke(cli, ["score-conditions", "global-regime-v1"]).exit_code == 0

    label_result = cli_runner.invoke(cli, ["run-label-program", "canonical-direction-v1"])
    assert label_result.exit_code == 0

    session = get_session(settings)
    try:
        run = session.query(ExperimentRun).filter_by(experiment_name="label_program_v1").one()
        proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(source_owner_type="experiment_run", source_owner_key=run.run_id)
            .one()
        )
    finally:
        session.close()

    assert cli_runner.invoke(cli, ["review-proposal", proposal.proposal_id]).exit_code == 0

    result = cli_runner.invoke(
        cli,
        [
            "compare-proposals",
            "--proposal-id",
            proposal.proposal_id,
            "--choose-top",
        ],
    )
    assert result.exit_code == 0
    assert proposal.proposal_id in result.output

    receipt = json.loads(
        (
            settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "research_proposal_priority_receipt.json"
        ).read_text()
    )
    assert receipt["selected_proposal_id"] == proposal.proposal_id
