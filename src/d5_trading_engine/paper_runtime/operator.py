"""Bounded paper-trading operator loop over advisory strategy output."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.execution_intent.owner import ExecutionIntentOwner
from d5_trading_engine.policy.global_regime_v1 import GlobalRegimePolicyEvaluator
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.proposals import create_improvement_proposal
from d5_trading_engine.reporting.qmd import render_qmd
from d5_trading_engine.research_loop.registries import load_strategy_registry
from d5_trading_engine.risk.gate import RiskGate
from d5_trading_engine.settlement.paper import PaperSettlement
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import QuoteSnapshot

_DEFAULT_STRATEGY_REPORT = (
    Path(".ai") / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json"
)
_BUY_DIRECTIONS = {"buy", "usdc_to_token"}
_SELL_DIRECTIONS = {"sell", "token_to_usdc"}


class PaperTradeOperator:
    """Controlled paper-only operator loop for one explicit paper cycle."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def run_cycle(
        self,
        *,
        quote_snapshot_id: int,
        strategy_report_path: Path | None = None,
        condition_run_id: str | None = None,
    ) -> dict[str, object]:
        """Run one bounded paper-trading cycle from advisory output to settlement."""

        cycle_started_at = utcnow()
        advisory_selection = self._load_advisory_strategy_selection(
            strategy_report_path=strategy_report_path
        )
        quote_summary = self._load_quote_summary(quote_snapshot_id=quote_snapshot_id)

        policy_result = GlobalRegimePolicyEvaluator(self.settings).evaluate(
            condition_run_id=condition_run_id
        )
        risk_result = RiskGate(self.settings).evaluate_global_regime_v1(
            policy_trace_id=policy_result["trace_id"]
        )
        risk_verdict_id = risk_result.get("risk_verdict_id")
        if risk_verdict_id is None:
            raise RuntimeError("Risk gate did not persist a risk verdict for the paper cycle.")

        execution_intent = ExecutionIntentOwner(self.settings).create_spot_intent(
            risk_verdict_id=int(risk_verdict_id),
            quote_snapshot_id=quote_snapshot_id,
            intent_created_at=cycle_started_at,
        )
        settlement_result = PaperSettlement(self.settings).simulate_fill(
            execution_intent_id=int(execution_intent["execution_intent_id"]),
            settlement_attempted_at=cycle_started_at,
        )
        portfolio_state = PaperSettlement(self.settings).get_portfolio_state(
            settlement_result["session_key"]
        )
        strategy_alignment = self._build_strategy_alignment(
            advisory_selection=advisory_selection,
            quote_summary=quote_summary,
            policy_result=policy_result,
            risk_result=risk_result,
            execution_intent=execution_intent,
            settlement_result=settlement_result,
        )

        artifact_dir = self._artifact_dir(str(settlement_result["session_key"]))
        artifact_dir.mkdir(parents=True, exist_ok=True)

        config_payload = {
            "paper_cycle_started_at_utc": cycle_started_at.isoformat(),
            "quote_snapshot_id": quote_snapshot_id,
            "condition_run_id": condition_run_id,
            "strategy_report_path": advisory_selection["report_path"],
            "artifact_dir": str(artifact_dir),
        }
        cycle_summary = {
            "session_key": settlement_result["session_key"],
            "session_status": settlement_result["session_status"],
            "filled": settlement_result["filled"],
            "artifact_dir": str(artifact_dir),
            "strategy_selection": advisory_selection,
            "quote_summary": quote_summary,
            "strategy_alignment": strategy_alignment,
            "policy_result": policy_result,
            "risk_result": risk_result,
            "execution_intent": execution_intent,
            "settlement_result": settlement_result,
            "portfolio_state": portfolio_state,
        }

        owner_type = "paper_session"
        owner_key = str(settlement_result["session_key"])

        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "advisory_strategy_selection.json",
            advisory_selection,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_strategy_selection",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "quote_snapshot_summary.json",
            quote_summary,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_quote_summary",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "strategy_alignment.json",
            strategy_alignment,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_strategy_alignment",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "policy_result.json",
            policy_result,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_policy_result",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "risk_result.json",
            risk_result,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_risk_result",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "execution_intent.json",
            execution_intent,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_execution_intent",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "settlement_result.json",
            settlement_result,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_settlement_result",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "portfolio_state.json",
            portfolio_state,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_portfolio_state",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            self._render_report_qmd(
                cycle_started_at=cycle_started_at,
                config_payload=config_payload,
                advisory_selection=advisory_selection,
                quote_summary=quote_summary,
                strategy_alignment=strategy_alignment,
                policy_result=policy_result,
                risk_result=risk_result,
                execution_intent=execution_intent,
                settlement_result=settlement_result,
                portfolio_state=portfolio_state,
            ),
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        proposal = create_improvement_proposal(
            artifact_dir=artifact_dir,
            proposal_kind="paper_cycle_follow_on",
            source_owner_type=owner_type,
            source_owner_key=owner_key,
            governance_scope="paper_runtime",
            title="Review bounded paper-cycle evidence before the next session",
            summary=(
                "The paper cycle completed with explicit policy, risk, settlement, and "
                "portfolio receipts. Any next action should remain reviewable and "
                "operator-approved."
            ),
            hypothesis=(
                "Constraining follow-on tests to the current top family and regime-aligned "
                "quotes should improve paper-session consistency without widening live "
                "authority."
            ),
            next_test=(
                "Review the paper-cycle evidence packet and approve one bounded follow-on "
                "paper session or backtest."
            ),
            metrics={
                "filled": 1.0 if settlement_result["filled"] else 0.0,
                "regime_aligned": 1.0 if strategy_alignment["regime_aligned"] else 0.0,
                "actionable_long_entry": 1.0
                if strategy_alignment["actionable_long_entry"]
                else 0.0,
                "equity_usdc": float(portfolio_state.get("total_value_usdc") or 0.0),
            },
            reason_codes=[
                "operator_review_required",
                "proposal_only_follow_on",
                "paper_trading_only",
            ],
            settings=self.settings,
        )
        cycle_summary["proposal_id"] = proposal["proposal_id"]
        cycle_summary["proposal_status"] = proposal["status"]
        write_json_artifact(
            artifact_dir / "cycle_summary.json",
            cycle_summary,
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type="paper_cycle_summary",
            settings=self.settings,
        )

        return cycle_summary

    def _load_advisory_strategy_selection(
        self,
        *,
        strategy_report_path: Path | None,
    ) -> dict[str, object]:
        report_path = strategy_report_path or (self.settings.repo_root / _DEFAULT_STRATEGY_REPORT)
        if not report_path.exists():
            raise RuntimeError(f"Missing advisory strategy report: {report_path}")

        payload = orjson.loads(report_path.read_bytes())
        if not isinstance(payload, dict):
            raise RuntimeError(f"Advisory strategy report must decode to an object: {report_path}")

        top_family = payload.get("top_family")
        if not isinstance(top_family, str) or not top_family.strip():
            raise RuntimeError(
                "Advisory strategy report does not contain a selected top_family."
            )
        top_family = top_family.strip()

        families = payload.get("families")
        if not isinstance(families, dict):
            raise RuntimeError(
                f"Advisory strategy report families payload is invalid: {report_path}"
            )
        selected_metrics = families.get(top_family)
        if not isinstance(selected_metrics, dict):
            raise RuntimeError(
                f"Selected top_family is missing from advisory metrics: {top_family}"
            )

        strategy_registry = load_strategy_registry(self.settings.repo_root)
        registry_families = strategy_registry.get("families")
        if not isinstance(registry_families, dict):
            raise RuntimeError("Strategy registry is missing the families mapping.")
        family_config = registry_families.get(top_family)
        if not isinstance(family_config, dict):
            raise RuntimeError(f"Strategy registry is missing the selected family: {top_family}")

        allowed_regimes = family_config.get("allowed_regimes") or []
        if not isinstance(allowed_regimes, list):
            raise RuntimeError(f"Selected family allowed_regimes is invalid: {top_family}")

        return {
            "report_path": str(report_path),
            "run_id": payload.get("run_id"),
            "generated_at": payload.get("generated_at"),
            "auto_promotion_eligible": bool(payload.get("auto_promotion_eligible")),
            "top_family": top_family,
            "family_metrics": selected_metrics,
            "instrument_scope": family_config.get("instrument_scope"),
            "venue": family_config.get("venue"),
            "label_family": family_config.get("label_family"),
            "target_label": family_config.get("target_label"),
            "allowed_regimes": [str(item) for item in allowed_regimes],
            "feature_sets": [str(item) for item in (family_config.get("feature_sets") or [])],
            "require_anomaly_veto": bool(family_config.get("require_anomaly_veto")),
        }

    def _load_quote_summary(self, *, quote_snapshot_id: int) -> dict[str, object]:
        session = get_session(self.settings)
        try:
            row = session.query(QuoteSnapshot).filter_by(id=quote_snapshot_id).first()
            if row is None:
                raise RuntimeError(f"Missing quote snapshot for paper cycle: {quote_snapshot_id}")
            return {
                "quote_snapshot_id": row.id,
                "provider": row.provider,
                "input_mint": row.input_mint,
                "input_symbol": self._symbol_for_mint(row.input_mint),
                "output_mint": row.output_mint,
                "output_symbol": self._symbol_for_mint(row.output_mint),
                "input_amount": row.input_amount,
                "output_amount": row.output_amount,
                "price_impact_pct": row.price_impact_pct,
                "slippage_bps": row.slippage_bps,
                "request_direction": row.request_direction,
                "request_direction_normalized": self._normalize_direction(row.request_direction),
                "requested_at": self._iso_datetime(row.requested_at),
                "captured_at": self._iso_datetime(row.captured_at),
            }
        finally:
            session.close()

    def _build_strategy_alignment(
        self,
        *,
        advisory_selection: dict[str, object],
        quote_summary: dict[str, object],
        policy_result: dict[str, object],
        risk_result: dict[str, object],
        execution_intent: dict[str, object],
        settlement_result: dict[str, object],
    ) -> dict[str, object]:
        target_label = str(advisory_selection.get("target_label") or "")
        semantic_regime = str(policy_result.get("semantic_regime") or "")
        allowed_regimes = {
            str(item) for item in (advisory_selection.get("allowed_regimes") or [])
        }
        policy_state = str(policy_result.get("policy_state") or "")
        quote_direction = str(quote_summary.get("request_direction_normalized") or "")

        expected_quote_direction = "usdc_to_token"
        if target_label == "down":
            expected_quote_direction = "token_to_usdc"
        elif target_label == "flat":
            expected_quote_direction = "stand_aside"

        actionable_long_entry = (
            target_label == "up"
            and semantic_regime in allowed_regimes
            and policy_state == "eligible_long"
            and quote_direction == "usdc_to_token"
            and bool(risk_result.get("allowed"))
            and bool(execution_intent.get("ready"))
            and bool(settlement_result.get("filled"))
        )

        return {
            "semantic_regime": semantic_regime,
            "policy_state": policy_state,
            "strategy_top_family": advisory_selection.get("top_family"),
            "strategy_target_label": target_label,
            "strategy_allowed_regimes": sorted(allowed_regimes),
            "regime_aligned": semantic_regime in allowed_regimes,
            "expected_quote_direction": expected_quote_direction,
            "quote_direction_aligned": expected_quote_direction == quote_direction,
            "quote_direction_normalized": quote_direction,
            "runtime_long_entry_supported": target_label == "up",
            "actionable_long_entry": actionable_long_entry,
        }

    def _artifact_dir(self, session_key: str) -> Path:
        return self.settings.data_dir / "paper_runtime" / "cycles" / session_key

    def _render_report_qmd(
        self,
        *,
        cycle_started_at,
        config_payload: dict[str, object],
        advisory_selection: dict[str, object],
        quote_summary: dict[str, object],
        strategy_alignment: dict[str, object],
        policy_result: dict[str, object],
        risk_result: dict[str, object],
        execution_intent: dict[str, object],
        settlement_result: dict[str, object],
        portfolio_state: dict[str, object],
    ) -> str:
        strategy_lines = [
            f"- advisory report: `{advisory_selection['report_path']}`",
            f"- top family: `{advisory_selection['top_family']}`",
            f"- target label: `{advisory_selection['target_label']}`",
            f"- venue: `{advisory_selection['venue']}`",
            f"- instrument scope: `{advisory_selection['instrument_scope']}`",
            f"- allowed regimes: `{', '.join(advisory_selection['allowed_regimes']) or 'none'}`",
            f"- auto-promotion eligible: `{advisory_selection['auto_promotion_eligible']}`",
        ]
        quote_lines = [
            f"- quote snapshot id: `{quote_summary['quote_snapshot_id']}`",
            f"- pair: `{quote_summary['input_symbol']}` -> `{quote_summary['output_symbol']}`",
            f"- provider: `{quote_summary['provider']}`",
            f"- direction: `{quote_summary['request_direction_normalized']}`",
            f"- input amount: `{quote_summary['input_amount']}`",
            f"- output amount: `{quote_summary['output_amount']}`",
            f"- captured at: `{quote_summary['captured_at']}`",
        ]
        policy_lines = [
            f"- condition run: `{policy_result['condition_run_id']}`",
            f"- semantic regime: `{policy_result['semantic_regime']}`",
            f"- policy state: `{policy_result['policy_state']}`",
            f"- risk state: `{risk_result['risk_state']}`",
            f"- risk allowed: `{risk_result['allowed']}`",
        ]
        intent_lines = [
            f"- execution intent id: `{execution_intent['execution_intent_id']}`",
            f"- intent state: `{execution_intent['intent_state']}`",
            f"- settlement model: `{execution_intent['settlement_model']}`",
            f"- quote size lamports: `{execution_intent['quote_size_lamports']}`",
        ]
        settlement_lines = [
            f"- session key: `{settlement_result['session_key']}`",
            f"- session status: `{settlement_result['session_status']}`",
            f"- filled: `{settlement_result['filled']}`",
            f"- session id: `{settlement_result['session_id']}`",
            f"- report id: `{settlement_result['report_id']}`",
        ]
        portfolio_lines = [
            f"- cash usdc: `{portfolio_state.get('cash_usdc')}`",
            f"- position value usdc: `{portfolio_state.get('position_value_usdc')}`",
            f"- total value usdc: `{portfolio_state.get('total_value_usdc')}`",
            f"- positions: `{len(portfolio_state.get('positions') or [])}`",
        ]
        risk_lines = self._reason_lines(
            title="Risk reason codes",
            codes=[str(item) for item in (risk_result.get("reason_codes") or [])],
        )
        intent_reason_lines = self._reason_lines(
            title="Execution intent reason codes",
            codes=[str(item) for item in (execution_intent.get("reason_codes") or [])],
        )
        settlement_reason_lines = self._reason_lines(
            title="Settlement reason codes",
            codes=[str(item) for item in (settlement_result.get("reason_codes") or [])],
        )
        open_risks = [
            "- mint selection remains explicit via `quote_snapshot_id`; the advisory selector is still family-level only",
            "- the current runtime owner supports bounded spot long-entry semantics only; short and stand-aside advisories resolve as no-trade receipts",
        ]

        return render_qmd(
            "paper_cycle.qmd",
            title="paper_trade_cycle",
            generated_at=cycle_started_at,
            summary_lines=[
                f"- started at utc: `{config_payload['paper_cycle_started_at_utc']}`",
                f"- artifact dir: `{config_payload['artifact_dir']}`",
            ],
            sections=[
                ("Advisory Strategy", strategy_lines),
                ("Quote Input", quote_lines),
                (
                    "Policy and Risk",
                    [
                        *policy_lines,
                        f"- regime aligned: `{strategy_alignment['regime_aligned']}`",
                        f"- actionable long entry: `{strategy_alignment['actionable_long_entry']}`",
                    ],
                ),
                ("Risk reason codes", [item for item in risk_lines if not item.startswith("## ")]),
                ("Execution Intent", intent_lines),
                (
                    "Execution intent reason codes",
                    [item for item in intent_reason_lines if not item.startswith("## ")],
                ),
                ("Settlement", settlement_lines),
                (
                    "Settlement reason codes",
                    [item for item in settlement_reason_lines if not item.startswith("## ")],
                ),
                ("Portfolio Snapshot", portfolio_lines),
                ("Open Risks", open_risks),
            ],
        )

    def _reason_lines(self, *, title: str, codes: list[str]) -> list[str]:
        if not codes:
            return [f"## {title}", "", "- none"]
        return [f"## {title}", "", *[f"- `{code}`" for code in codes]]

    def _symbol_for_mint(self, mint: str) -> str:
        return self.settings.token_symbol_hints.get(mint, mint[:8])

    def _normalize_direction(self, value: str | None) -> str | None:
        if value in _BUY_DIRECTIONS:
            return "usdc_to_token"
        if value in _SELL_DIRECTIONS:
            return "token_to_usdc"
        return None

    def _iso_datetime(self, value: Any) -> str | None:
        dt = ensure_utc(value)
        return dt.isoformat() if dt is not None else None
