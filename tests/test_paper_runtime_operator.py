from __future__ import annotations

import json
from datetime import timedelta

from d5_trading_engine.cli import cli
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    ExecutionIntentV1,
    FeatureMaterializationRun,
    ImprovementProposalV1,
    PaperFill,
    PaperSession,
    QuoteSnapshot,
    RiskGlobalRegimeGateV1,
)
from d5_trading_engine.paper_runtime.operator import PaperTradeOperator
from tests.test_label_strategy_loop import _seed_research_repo_truth
from tests.test_settlement_paper import (
    _freshness_snapshot,
    _seed_quote_snapshot,
    _tracked_mint,
)


def _seed_condition_run(settings, *, run_id: str, semantic_regime: str) -> str:
    session = get_session(settings)
    now = utcnow().replace(second=0, microsecond=0)
    started_at = now - timedelta(minutes=10)
    finished_at = started_at + timedelta(minutes=1)
    feature_run_id = f"feature_{run_id}"
    try:
        session.add(
            FeatureMaterializationRun(
                run_id=feature_run_id,
                feature_set="global_regime_inputs_15m_v1",
                source_tables="[]",
                freshness_snapshot_json=json.dumps(_freshness_snapshot()),
                status="success",
                started_at=started_at - timedelta(minutes=30),
                finished_at=started_at - timedelta(minutes=29),
                created_at=started_at - timedelta(minutes=30),
            )
        )
        session.flush()
        session.add(
            ConditionScoringRun(
                run_id=run_id,
                condition_set="global_regime_v1",
                source_feature_run_id=feature_run_id,
                model_family="gaussian_hmm_4state",
                status="success",
                confidence=0.81,
                started_at=started_at,
                finished_at=finished_at,
                created_at=started_at,
            )
        )
        session.flush()
        session.add(
            ConditionGlobalRegimeSnapshotV1(
                condition_run_id=run_id,
                source_feature_run_id=feature_run_id,
                bucket_start_utc=started_at - timedelta(minutes=15),
                raw_state_id=1,
                semantic_regime=semantic_regime,
                confidence=0.81,
                blocked_flag=0,
                blocking_reason=None,
                model_family="gaussian_hmm_4state",
                macro_context_state="healthy_recent",
                created_at=finished_at,
            )
        )
        session.commit()
    finally:
        session.close()
    return run_id


def _write_strategy_report(repo_root) -> None:
    report_path = (
        repo_root / ".ai" / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "artifact_type": "strategy_challenger_report",
                "run_id": "experiment_strategy_eval_seeded",
                "story_id": "STRAT-001",
                "stage": "strategy_research",
                "families": {
                    "trend_continuation_long_v1": {
                        "rows_total": 48,
                        "rows_train": 32,
                        "rows_test": 16,
                        "anomaly_filter_applied": 1,
                        "rf_accuracy": 0.62,
                        "rf_auc": 0.64,
                        "xgb_accuracy": 0.68,
                        "xgb_auc": 0.71,
                        "positive_expectancy": 0.03,
                        "eligible": True,
                        "label_family": "direction_60m_v1",
                        "target_label": "up",
                        "allowed_regimes": ["long_friendly"],
                    }
                },
                "top_family": "trend_continuation_long_v1",
                "auto_promotion_eligible": True,
                "generated_at": utcnow().isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_cli_run_paper_cycle_creates_paper_truth_and_qmd(cli_runner, settings) -> None:
    _seed_research_repo_truth(settings.repo_root)
    run_migrations_to_head(settings)
    condition_run_id = _seed_condition_run(
        settings,
        run_id="condition_long_paper_cycle",
        semantic_regime="long_friendly",
    )
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_paper_cycle_long",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )
    _write_strategy_report(settings.repo_root)

    result = cli_runner.invoke(
        cli,
        [
            "run-paper-cycle",
            str(quote_snapshot_id),
            "--condition-run-id",
            condition_run_id,
        ],
    )

    assert result.exit_code == 0
    assert "paper_cycle:" in result.output
    assert "top_family=trend_continuation_long_v1" in result.output

    session = get_session(settings)
    try:
        quote_row = session.query(QuoteSnapshot).filter_by(id=quote_snapshot_id).one()
        risk_row = session.query(RiskGlobalRegimeGateV1).one()
        intent_row = session.query(ExecutionIntentV1).one()
        paper_session = session.query(PaperSession).one()
        paper_fill = session.query(PaperFill).one()
        proposal = (
            session.query(ImprovementProposalV1)
            .filter_by(
                source_owner_type="paper_session",
                source_owner_key=paper_session.session_key,
            )
            .one()
        )
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="paper_session", owner_key=paper_session.session_key)
            .all()
        )
    finally:
        session.close()

    assert quote_row.id == quote_snapshot_id
    assert risk_row.risk_state == "allowed"
    assert intent_row.intent_state == "ready"
    assert paper_session.status == "open"
    assert paper_fill.quote_snapshot_id == quote_snapshot_id
    assert proposal.status == "proposed"
    assert proposal.runtime_effect == "advisory_only"
    assert artifacts

    artifact_dir = settings.data_dir / "paper_runtime" / "cycles" / paper_session.session_key
    assert artifact_dir.exists()
    assert (artifact_dir / "config.json").exists()
    assert (artifact_dir / "advisory_strategy_selection.json").exists()
    assert (artifact_dir / "cycle_summary.json").exists()
    assert (artifact_dir / "report.qmd").exists()

    cycle_summary = json.loads((artifact_dir / "cycle_summary.json").read_text())
    assert cycle_summary["filled"] is True
    assert cycle_summary["strategy_selection"]["top_family"] == "trend_continuation_long_v1"
    assert cycle_summary["strategy_alignment"]["actionable_long_entry"] is True
    assert cycle_summary["proposal_status"] == "proposed"
    assert "proposal_id" in cycle_summary

    assert (artifact_dir / "proposal.json").exists()
    assert (artifact_dir / "proposal.qmd").exists()

    report_text = (artifact_dir / "report.qmd").read_text(encoding="utf-8")
    assert "trend_continuation_long_v1" in report_text
    assert paper_session.session_key in report_text


def test_cli_run_paper_cycle_fails_closed_without_strategy_report(cli_runner, settings) -> None:
    run_migrations_to_head(settings)
    condition_run_id = _seed_condition_run(
        settings,
        run_id="condition_missing_strategy_report",
        semantic_regime="long_friendly",
    )
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_missing_strategy_report",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )

    result = cli_runner.invoke(
        cli,
        [
            "run-paper-cycle",
            str(quote_snapshot_id),
            "--condition-run-id",
            condition_run_id,
        ],
    )

    assert result.exit_code == 1
    assert "Missing advisory strategy report" in result.output


def test_paper_trade_operator_close_cycle_writes_close_artifacts(settings) -> None:
    _seed_research_repo_truth(settings.repo_root)
    run_migrations_to_head(settings)
    condition_run_id = _seed_condition_run(
        settings,
        run_id="condition_close_operator",
        semantic_regime="long_friendly",
    )
    usdc_mint = _tracked_mint(settings, "USDC")
    sol_mint = _tracked_mint(settings, "SOL")
    entry_quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_operator_entry",
        request_direction="usdc_to_token",
        input_mint=usdc_mint,
        output_mint=sol_mint,
        input_amount="10000000",
        output_amount="100000000",
    )
    _write_strategy_report(settings.repo_root)

    opened = PaperTradeOperator(settings).run_cycle(
        quote_snapshot_id=entry_quote_snapshot_id,
        condition_run_id=condition_run_id,
    )

    close_quote_snapshot_id = _seed_quote_snapshot(
        settings,
        run_id="quote_operator_exit",
        request_direction="token_to_usdc",
        input_mint=sol_mint,
        output_mint=usdc_mint,
        input_amount="100000000",
        output_amount="10300000",
    )
    closed = PaperTradeOperator(settings).close_cycle(
        session_key=str(opened["session_key"]),
        quote_snapshot_id=close_quote_snapshot_id,
        close_reason="take_profit",
        condition_run_id=condition_run_id,
    )

    assert closed["settlement_result"]["closed"] is True
    assert closed["settlement_result"]["session_status"] == "closed"

    artifact_dir = settings.data_dir / "paper_runtime" / "cycles" / str(opened["session_key"])
    assert (artifact_dir / "close_summary.json").exists()
    assert (artifact_dir / "close_report.qmd").exists()

    session = get_session(settings)
    try:
        paper_session = session.query(PaperSession).one()
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="paper_session", owner_key=str(opened["session_key"]))
            .all()
        )
    finally:
        session.close()

    assert paper_session.status == "closed"
    artifact_types = {artifact.artifact_type for artifact in artifacts}
    assert "paper_close_summary" in artifact_types
    assert "paper_close_report_qmd" in artifact_types
