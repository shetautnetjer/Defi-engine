from __future__ import annotations

import asyncio
import json

from d5_trading_engine.research_loop.live_regime_cycle import LiveRegimeCycleRunner
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import (
    ArtifactReference,
    ImprovementProposalV1,
    IngestRun,
    QuoteSnapshot,
)


def test_live_regime_cycle_writes_paper_ready_receipt(settings, monkeypatch) -> None:
    run_migrations_to_head(settings)
    session = get_session(settings)
    try:
        from d5_trading_engine.common.time_utils import utcnow

        timestamp = utcnow()
        session.add(
            IngestRun(
                run_id="quote_run_live_001",
                provider="jupiter",
                capture_type="quotes",
                status="success",
                started_at=timestamp,
                finished_at=timestamp,
                records_captured=1,
                created_at=timestamp,
            )
        )
        session.add(
            QuoteSnapshot(
                ingest_run_id="quote_run_live_001",
                input_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                output_mint="So11111111111111111111111111111111111111112",
                input_amount="1000000",
                output_amount="6500",
                price_impact_pct=0.12,
                slippage_bps=50,
                route_plan_json="[]",
                other_amount_threshold="0",
                swap_mode="ExactIn",
                request_direction="usdc_to_token",
                requested_at=timestamp,
                response_latency_ms=25.0,
                source_event_time_utc=timestamp,
                source_time_raw=timestamp.isoformat(),
                event_date_utc=timestamp.strftime("%Y-%m-%d"),
                hour_utc=timestamp.hour,
                minute_of_day_utc=(timestamp.hour * 60) + timestamp.minute,
                weekday_utc=timestamp.weekday(),
                time_quality="source",
                provider="jupiter",
                captured_at=timestamp,
            )
        )
        session.commit()
    finally:
        session.close()

    async def _fake_capture(self):
        return "capture_run_test"

    def _noop_receipts(self, run_id: str, *, context=None):
        assert run_id == "capture_run_test"
        return None

    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_jupiter_prices",
        _fake_capture,
    )
    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_jupiter_quotes",
        _fake_capture,
    )
    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_helius_transactions",
        _fake_capture,
    )
    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_coinbase_candles",
        _fake_capture,
    )
    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_coinbase_book",
        _fake_capture,
    )
    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.capture_coinbase_market_trades",
        _fake_capture,
    )
    monkeypatch.setattr(
        "d5_trading_engine.capture.runner.CaptureRunner.write_capture_receipts",
        _noop_receipts,
    )
    monkeypatch.setattr(
        "d5_trading_engine.features.materializer.FeatureMaterializer.materialize_global_regime_inputs_15m_v1",
        lambda self: ("feature_global_test", 128),
    )
    monkeypatch.setattr(
        "d5_trading_engine.features.materializer.FeatureMaterializer.materialize_spot_chain_macro_v1",
        lambda self: ("feature_spot_test", 64),
    )
    monkeypatch.setattr(
        "d5_trading_engine.condition.scorer.ConditionScorer.score_global_regime_v1",
        lambda self: {
            "run_id": "condition_run_test",
            "latest_snapshot": {"semantic_regime": "long_friendly"},
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.research_loop.regime_model_compare.RegimeModelComparator.run_regime_model_compare_v1",
        lambda self: {
            "run_id": "experiment_regime_compare_test",
            "artifact_dir": str(settings.data_dir / "research" / "regime_model_compare" / "test"),
            "recommended_candidate": "hmm",
            "proposal_status": "proposed",
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.policy.global_regime_v1.GlobalRegimePolicyEvaluator.evaluate",
        lambda self, condition_run_id=None: {
            "trace_id": 7,
            "policy_state": "eligible_long",
            "condition_run_id": condition_run_id,
        },
    )
    monkeypatch.setattr(
        "d5_trading_engine.risk.gate.RiskGate.evaluate_global_regime_v1",
        lambda self, policy_trace_id=None: {
            "risk_verdict_id": 9,
            "risk_state": "allowed",
            "policy_trace_id": policy_trace_id,
        },
    )

    result = asyncio.run(LiveRegimeCycleRunner(settings).run_live_regime_cycle())

    assert result["ready_for_paper_cycle"] is True
    assert result["quote_snapshot_id"] is not None

    artifact_dir = settings.data_dir / "research" / "live_regime_cycle" / result["cycle_id"]
    paper_ready = json.loads((artifact_dir / "paper_ready_receipt.json").read_text(encoding="utf-8"))
    assert paper_ready["policy_state"] == "eligible_long"
    assert paper_ready["risk_state"] == "allowed"
    assert paper_ready["quote_snapshot_id"] is not None
    assert "run-paper-cycle" in paper_ready["paper_cycle_command"]

    session = get_session(settings)
    try:
        proposal = session.query(ImprovementProposalV1).one()
        artifacts = (
            session.query(ArtifactReference)
            .filter_by(owner_type="live_regime_cycle", owner_key=result["cycle_id"])
            .all()
        )
    finally:
        session.close()

    assert proposal.proposal_kind == "live_regime_cycle_follow_on"
    assert {artifact.artifact_type for artifact in artifacts} == {
        "live_regime_cycle_config",
        "live_regime_cycle_summary",
        "live_regime_cycle_paper_ready_receipt",
        "live_regime_cycle_report_qmd",
    }
