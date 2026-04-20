"""Micro-live readiness gate evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.config.settings import Settings


class LiveReadinessService:
    """Evaluate whether paper evidence is strong enough for micro-live arming."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @property
    def default_metrics_path(self) -> Path:
        return (
            self.settings.data_dir
            / "research"
            / "training"
            / "live_readiness"
            / "latest_metrics.json"
        )

    def evaluate(self, metrics_path: Path | None = None) -> dict[str, Any]:
        """Return a fail-closed readiness decision from the latest metrics packet."""

        path = metrics_path or self.default_metrics_path
        thresholds = self._thresholds()
        if not path.exists():
            return self._decision(
                passed=False,
                reason_codes=["live_readiness_metrics_missing"],
                thresholds=thresholds,
                metrics={},
                metrics_path=path,
            )

        metrics = orjson.loads(path.read_bytes())
        reason_codes = self._reason_codes(metrics, thresholds)
        return self._decision(
            passed=not reason_codes,
            reason_codes=reason_codes,
            thresholds=thresholds,
            metrics=metrics,
            metrics_path=path,
        )

    def _thresholds(self) -> dict[str, Any]:
        return {
            "minimum_rolling_win_rate": 0.8,
            "minimum_settled_trades": 20,
            "minimum_average_settled_trades_per_week": 1.0,
            "minimum_consecutive_trade_weeks": 4,
            "minimum_net_expectancy_after_cost": 0.0,
            "minimum_profit_factor": 1.5,
            "maximum_drawdown_pct": self.settings.micro_live_max_drawdown_pct,
            "required_quote_health_ok": True,
            "maximum_unexplained_decision_gap_count": 0,
            "requires_candidate_comparison_accepted": True,
        }

    def _reason_codes(
        self,
        metrics: dict[str, Any],
        thresholds: dict[str, Any],
    ) -> list[str]:
        reason_codes: list[str] = []
        if float(metrics.get("rolling_win_rate", 0.0)) < thresholds["minimum_rolling_win_rate"]:
            reason_codes.append("rolling_win_rate_below_minimum")
        if int(metrics.get("settled_trades", 0)) < thresholds["minimum_settled_trades"]:
            reason_codes.append("settled_trades_below_minimum")
        if (
            float(metrics.get("average_settled_trades_per_week", 0.0))
            < thresholds["minimum_average_settled_trades_per_week"]
        ):
            reason_codes.append("average_settled_trades_per_week_below_minimum")
        if int(metrics.get("consecutive_trade_weeks", 0)) < thresholds[
            "minimum_consecutive_trade_weeks"
        ]:
            reason_codes.append("consecutive_trade_weeks_below_minimum")
        if (
            float(metrics.get("net_expectancy_after_cost", 0.0))
            <= thresholds["minimum_net_expectancy_after_cost"]
        ):
            reason_codes.append("net_expectancy_after_cost_not_positive")
        if float(metrics.get("profit_factor", 0.0)) < thresholds["minimum_profit_factor"]:
            reason_codes.append("profit_factor_below_minimum")
        if float(metrics.get("max_drawdown_pct", 100.0)) > thresholds["maximum_drawdown_pct"]:
            reason_codes.append("max_drawdown_pct_above_maximum")
        if bool(metrics.get("quote_health_ok", False)) is not True:
            reason_codes.append("quote_health_not_ok")
        if (
            int(metrics.get("unexplained_decision_gap_count", 1))
            > thresholds["maximum_unexplained_decision_gap_count"]
        ):
            reason_codes.append("unexplained_decision_gaps_present")
        if bool(metrics.get("candidate_comparison_accepted", False)) is not True:
            reason_codes.append("candidate_comparison_not_accepted")
        return reason_codes

    def _decision(
        self,
        *,
        passed: bool,
        reason_codes: list[str],
        thresholds: dict[str, Any],
        metrics: dict[str, Any],
        metrics_path: Path,
    ) -> dict[str, Any]:
        return {
            "status": "passed" if passed else "failed",
            "passed": passed,
            "micro_live_candidate": passed,
            "reason_codes": reason_codes,
            "thresholds": thresholds,
            "metrics": metrics,
            "metrics_path": str(metrics_path),
            "evaluated_at_utc": datetime.now(UTC).isoformat(),
        }

