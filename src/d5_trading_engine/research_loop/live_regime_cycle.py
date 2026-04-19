"""Live intraday capture and retraining loop for paper-only regime trading."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import desc

from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.condition.scorer import ConditionScorer
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.features.materializer import FeatureMaterializer
from d5_trading_engine.policy.global_regime_v1 import GlobalRegimePolicyEvaluator
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.proposals import create_improvement_proposal
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata
from d5_trading_engine.research_loop.regime_model_compare import RegimeModelComparator
from d5_trading_engine.research_loop.training_events import append_training_event_safe
from d5_trading_engine.risk.gate import RiskGate
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import QuoteSnapshot

_DEFAULT_STRATEGY_REPORT = (
    Path(".ai") / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json"
)


class LiveRegimeCycleRunner:
    """Run a bounded live-capture to paper-ready training cycle."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def run_live_regime_cycle(self, *, with_helius_ws: bool = False) -> dict[str, Any]:
        cycle_id = f"live_regime_cycle_{utcnow().strftime('%Y%m%dT%H%M%S%fZ')}"
        artifact_dir = self.settings.data_dir / "research" / "live_regime_cycle" / cycle_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        capture_runner = CaptureRunner(self.settings)
        materializer = FeatureMaterializer(self.settings)
        scorer = ConditionScorer(self.settings)
        comparator = RegimeModelComparator(self.settings)

        capture_steps: list[dict[str, Any]] = []
        for label, capture_fn in (
            ("jupiter-prices", capture_runner.capture_jupiter_prices),
            ("jupiter-quotes", capture_runner.capture_jupiter_quotes),
            ("helius-transactions", capture_runner.capture_helius_transactions),
            ("coinbase-candles", capture_runner.capture_coinbase_candles),
            ("coinbase-book", capture_runner.capture_coinbase_book),
            ("coinbase-market-trades", capture_runner.capture_coinbase_market_trades),
        ):
            run_id = await capture_fn()
            capture_runner.write_capture_receipts(
                run_id,
                context={"requested_provider": label, "live_regime_cycle_id": cycle_id},
            )
            capture_steps.append({"lane": label, "run_id": run_id})

        if with_helius_ws:
            ws_run_id = await capture_runner.capture_helius_ws_events()
            capture_runner.write_capture_receipts(
                ws_run_id,
                context={"requested_provider": "helius-ws-events", "live_regime_cycle_id": cycle_id},
            )
            capture_steps.append({"lane": "helius-ws-events", "run_id": ws_run_id})

        global_feature_run_id, global_feature_rows = materializer.materialize_global_regime_inputs_15m_v1()
        spot_feature_run_id, spot_feature_rows = materializer.materialize_spot_chain_macro_v1()
        condition_result = scorer.score_global_regime_v1()
        comparison_result = comparator.run_regime_model_compare_v1()
        condition_summary = self._summarize_condition_result(condition_result)
        policy_result = GlobalRegimePolicyEvaluator(self.settings).evaluate(
            condition_run_id=str(condition_result["run_id"])
        )
        risk_result = RiskGate(self.settings).evaluate_global_regime_v1(
            policy_trace_id=int(policy_result["trace_id"])
        )
        paper_ready_receipt = self._build_paper_ready_receipt(
            condition_result=condition_result,
            comparison_result=comparison_result,
            policy_result=policy_result,
            risk_result=risk_result,
        )

        config_payload = {
            "cycle_id": cycle_id,
            "with_helius_ws": bool(with_helius_ws),
            "artifact_dir": str(artifact_dir),
            "execution_authority": "paper_only",
            "context_anchors": ["BTC/USD", "ETH/USD"],
            "paper_execution_pair": "SOL/USDC",
        }
        summary_payload = {
            "cycle_id": cycle_id,
            "capture_steps": capture_steps,
            "feature_runs": {
                "global_regime_inputs_15m_v1": {
                    "run_id": global_feature_run_id,
                    "row_count": global_feature_rows,
                },
                "spot_chain_macro_v1": {
                    "run_id": spot_feature_run_id,
                    "row_count": spot_feature_rows,
                },
            },
            "condition_result": condition_summary,
            "comparison_result": comparison_result,
            "policy_result": policy_result,
            "risk_result": risk_result,
            "paper_ready_receipt": paper_ready_receipt,
        }

        owner_type = "live_regime_cycle"
        owner_key = cycle_id
        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="live_regime_cycle_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "live_cycle_summary.json",
            summary_payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="live_regime_cycle_summary",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "paper_ready_receipt.json",
            paper_ready_receipt,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="live_regime_cycle_paper_ready_receipt",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "experiment_run.qmd",
                title="live_regime_cycle",
                metadata=trading_report_metadata(
                    report_kind="live_regime_cycle",
                    run_id=cycle_id,
                    owner_type=owner_type,
                    owner_key=owner_key,
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="15m",
                    summary_path="live_cycle_summary.json",
                    config_path="config.json",
                ),
                summary_lines=[
                    f"- cycle id: `{cycle_id}`",
                    f"- capture steps: `{len(capture_steps)}`",
                    f"- global feature rows: `{global_feature_rows}`",
                    f"- spot feature rows: `{spot_feature_rows}`",
                    f"- condition run id: `{condition_result['run_id']}`",
                    f"- comparison run id: `{comparison_result['run_id']}`",
                    f"- paper-ready quote snapshot id: `{paper_ready_receipt['quote_snapshot_id']}`",
                    f"- ready for paper cycle: `{paper_ready_receipt['ready_for_paper_cycle']}`",
                ],
                sections=[
                    (
                        "Market / Source Context",
                        [
                            f"- `{row['lane']}` -> `{row['run_id']}`"
                            for row in capture_steps
                        ]
                        or ["- none"],
                    ),
                    (
                        "Regime / Condition / Policy / Risk",
                        [
                            f"- semantic regime: `{condition_result['latest_snapshot']['semantic_regime']}`",
                            f"- recommended candidate: `{comparison_result['recommended_candidate']}`",
                            f"- policy state: `{policy_result['policy_state']}`",
                            f"- risk state: `{risk_result['risk_state']}`",
                        ],
                    ),
                    (
                        "Bounded Next Change",
                        [
                            f"- quote snapshot id: `{paper_ready_receipt['quote_snapshot_id']}`",
                            f"- strategy report path: `{paper_ready_receipt['recommended_strategy_report_path']}`",
                            f"- paper cycle command: `{paper_ready_receipt['paper_cycle_command']}`",
                        ],
                    ),
                ],
            ),
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="live_regime_cycle_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        append_training_event_safe(
            self.settings,
            event_type="feature_run_completed",
            summary="Feature materialization completed for the latest live regime cycle.",
            owner_kind="live_regime_cycle",
            run_id=cycle_id,
            qmd_reports=[artifact_dir / "report.qmd"],
            sql_refs=[
                f"feature_run:{global_feature_run_id}",
                f"feature_run:{spot_feature_run_id}",
            ],
            context_files=[
                Path("src/d5_trading_engine/research_loop/live_regime_cycle.py"),
                Path("src/d5_trading_engine/features/materializer.py"),
            ],
            notes=(
                "Review the newest feature materialization against the accepted baseline "
                "and keep, revert, or shadow one bounded feature/source surface."
            ),
        )
        append_training_event_safe(
            self.settings,
            event_type="condition_run_completed",
            summary="Condition scoring, policy tracing, and risk evaluation completed for the latest live regime cycle.",
            owner_kind="live_regime_cycle",
            run_id=str(condition_result["run_id"]),
            qmd_reports=[artifact_dir / "report.qmd"],
            sql_refs=[
                f"condition_run:{condition_result['run_id']}",
                f"policy_trace:{policy_result['trace_id']}",
                f"risk_verdict:{risk_result['risk_verdict_id']}",
            ],
            context_files=[
                Path("src/d5_trading_engine/research_loop/live_regime_cycle.py"),
                Path("src/d5_trading_engine/condition/scorer.py"),
                Path("src/d5_trading_engine/policy/global_regime_v1.py"),
                Path("src/d5_trading_engine/risk/gate.py"),
            ],
            notes=(
                "Review the latest condition and regime evidence, classify the weakest "
                "surface, and keep, revert, or shadow one bounded condition change."
            ),
        )
        proposal = create_improvement_proposal(
            artifact_dir=artifact_dir,
            proposal_kind="live_regime_cycle_follow_on",
            source_owner_type=owner_type,
            source_owner_key=owner_key,
            governance_scope="research_loop",
            title="Review the live intraday paper-ready receipt before the next explicit paper cycle",
            summary=(
                "The live intraday training cycle refreshed Jupiter, Helius, and Coinbase "
                "inputs, rebuilt features, rescored the bounded regime owner, and produced a "
                "paper-ready receipt without widening execution authority."
            ),
            hypothesis=(
                "Reviewing the freshest SOL/USDC quote together with the current policy, risk, "
                "and shadow-regime comparison should make the next paper cycle more repeatable "
                "without introducing live order routing."
            ),
            next_test=(
                "Review the paper-ready receipt and, if the policy and risk states remain "
                "eligible, run one explicit `d5 run-paper-cycle ...` invocation."
            ),
            metrics={
                "paper_ready_quote_present": (
                    1.0 if paper_ready_receipt["quote_snapshot_id"] is not None else 0.0
                ),
                "policy_eligible_long": 1.0 if policy_result["policy_state"] == "eligible_long" else 0.0,
                "risk_allowed": 1.0 if risk_result["risk_state"] == "allowed" else 0.0,
                "global_feature_rows": float(global_feature_rows),
                "spot_feature_rows": float(spot_feature_rows),
            },
            reason_codes=[
                "paper_trading_only",
                "operator_review_required",
                "proposal_only_follow_on",
            ],
            settings=self.settings,
        )
        summary_payload["proposal_id"] = proposal["proposal_id"]
        summary_payload["proposal_status"] = proposal["status"]
        write_json_artifact(
            artifact_dir / "live_cycle_summary.json",
            summary_payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="live_regime_cycle_summary",
            settings=self.settings,
        )
        return {
            "cycle_id": cycle_id,
            "artifact_dir": str(artifact_dir),
            "condition_run_id": condition_result["run_id"],
            "comparison_run_id": comparison_result["run_id"],
            "quote_snapshot_id": paper_ready_receipt["quote_snapshot_id"],
            "ready_for_paper_cycle": paper_ready_receipt["ready_for_paper_cycle"],
            "policy_state": policy_result["policy_state"],
            "risk_state": risk_result["risk_state"],
            "paper_ready_receipt": paper_ready_receipt,
            "proposal_id": proposal["proposal_id"],
            "proposal_status": proposal["status"],
        }

    def _summarize_condition_result(self, condition_result: dict[str, Any]) -> dict[str, Any]:
        """Persist only the durable JSON-safe subset of the condition output."""
        latest_snapshot = dict(condition_result.get("latest_snapshot", {}))
        return {
            "run_id": condition_result["run_id"],
            "model_family": condition_result.get("model_family"),
            "feature_run_id": condition_result.get("feature_run_id"),
            "latest_snapshot": latest_snapshot,
        }

    def _build_paper_ready_receipt(
        self,
        *,
        condition_result: dict[str, Any],
        comparison_result: dict[str, Any],
        policy_result: dict[str, Any],
        risk_result: dict[str, Any],
    ) -> dict[str, Any]:
        sol_mint = next(
            mint
            for mint, symbol in self.settings.token_symbol_hints.items()
            if symbol == "SOL"
        )
        usdc_mint = next(
            mint
            for mint, symbol in self.settings.token_symbol_hints.items()
            if symbol == "USDC"
        )
        strategy_report_path = self.settings.repo_root / _DEFAULT_STRATEGY_REPORT

        session = get_session(self.settings)
        try:
            quote = (
                session.query(QuoteSnapshot)
                .filter_by(input_mint=usdc_mint, output_mint=sol_mint)
                .order_by(
                    desc(QuoteSnapshot.source_event_time_utc),
                    desc(QuoteSnapshot.captured_at),
                    desc(QuoteSnapshot.id),
                )
                .first()
            )
        finally:
            session.close()

        quote_snapshot_id = int(quote.id) if quote is not None else None
        ready_for_paper_cycle = (
            quote_snapshot_id is not None
            and policy_result["policy_state"] == "eligible_long"
            and risk_result["risk_state"] == "allowed"
        )
        paper_cycle_command = (
            f"d5 run-paper-cycle {quote_snapshot_id} "
            f"--condition-run-id {condition_result['run_id']} "
            f"--strategy-report {strategy_report_path}"
            if quote_snapshot_id is not None
            else ""
        )
        return {
            "cycle_generated_at": utcnow().isoformat(),
            "quote_snapshot_id": quote_snapshot_id,
            "condition_run_id": condition_result["run_id"],
            "policy_trace_id": policy_result["trace_id"],
            "policy_state": policy_result["policy_state"],
            "risk_verdict_id": risk_result.get("risk_verdict_id"),
            "risk_state": risk_result["risk_state"],
            "recommended_strategy_report_path": str(strategy_report_path),
            "strategy_report_exists": strategy_report_path.exists(),
            "recommended_candidate": comparison_result["recommended_candidate"],
            "ready_for_paper_cycle": ready_for_paper_cycle,
            "paper_cycle_command": paper_cycle_command,
        }
