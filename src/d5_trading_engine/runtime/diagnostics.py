"""Decision-funnel diagnostics for training and paper-runtime review.

The diagnostics in this module are read-only over runtime authority surfaces.
They summarize SQL truth into reviewable JSON/QMD receipts so the research loop
can decide what to test next without silently changing policy, risk, or strategy.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

import orjson
from sqlalchemy import distinct, func

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings
from d5_trading_engine.paper_runtime.training_profiles import get_training_profile
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    FeatureGlobalRegimeInput15mV1,
    MarketCandle,
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
)

_REASON_SURFACE_PREFIXES: tuple[tuple[str, str, str], ...] = (
    (
        "strategy_target_not_runtime_long",
        "strategy_candidate_generation",
        "Run baseline candidate strategy and strategy/policy compatibility sweep.",
    ),
    (
        "strategy_regime_not_allowed",
        "strategy_candidate_generation",
        "Run baseline candidate strategy and strategy/policy compatibility sweep.",
    ),
    (
        "strategy_selection_unavailable",
        "strategy_candidate_generation",
        "Run always-candidate sanity baseline to prove the detector can emit opportunities.",
    ),
    (
        "condition_confidence_below_profile_minimum",
        "condition",
        "Run condition-threshold shadow overlay and inspect confidence distribution.",
    ),
    (
        "regime_not_allowed",
        "policy",
        "Run policy eligibility comparison for blocked regimes.",
    ),
    (
        "risk",
        "risk",
        "Run risk rejection histogram before changing any risk threshold.",
    ),
    (
        "quote",
        "quote_fill",
        "Audit quote freshness and quote availability separately from strategy quality.",
    ),
    (
        "paper_ready_receipt_not_actionable",
        "data",
        "Repair capture/training readiness before evaluating strategy behavior.",
    ),
    (
        "profile_cooldown_active",
        "policy",
        "Inspect paper-practice cadence and cooldown overlay evidence.",
    ),
)

_SURFACE_PRIORITIES = {
    "strategy_candidate_generation": 0,
    "condition": 1,
    "policy": 2,
    "risk": 3,
    "quote_fill": 4,
    "features": 5,
    "data": 6,
    "unknown": 99,
}


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [str(item) for item in payload]


def _load_json_object(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        payload = orjson.loads(raw)
    except orjson.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _reason_surface(reason_code: str) -> tuple[str, str]:
    for prefix, surface, action in _REASON_SURFACE_PREFIXES:
        if reason_code.startswith(prefix):
            return surface, action
    return "unknown", "Inspect raw decision reasons and add a typed diagnostic mapping."


def _ranked_counts(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"reason_code": code, "count": count}
        for code, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    ]


def _ranked_surfaces(counter: Counter[str]) -> list[dict[str, Any]]:
    return [
        {"surface": surface, "count": count}
        for surface, count in sorted(
            counter.items(),
            key=lambda item: (
                -item[1],
                _SURFACE_PRIORITIES.get(item[0], 99),
                item[0],
            ),
        )
    ]


def _top_reason_for_surface(
    reason_counts: Counter[str],
    *,
    surface: str,
) -> str | None:
    candidates = [
        (code, count)
        for code, count in reason_counts.items()
        if _reason_surface(code)[0] == surface
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (-item[1], item[0]))[0][0]


def _parse_window_days(window: str) -> int:
    normalized = window.strip().lower()
    if normalized.endswith("d"):
        normalized = normalized[:-1]
    days = int(normalized)
    if days <= 0:
        raise ValueError("window must be a positive day count, e.g. 300d")
    return days


def _latest_loop_run_id(settings: Settings) -> str | None:
    session = get_session(settings)
    try:
        latest_decision = (
            session.query(PaperPracticeDecisionV1)
            .order_by(
                PaperPracticeDecisionV1.created_at.desc(),
                PaperPracticeDecisionV1.id.desc(),
            )
            .first()
        )
        if latest_decision is not None:
            return str(latest_decision.loop_run_id)

        latest = (
            session.query(PaperPracticeLoopRunV1)
            .order_by(PaperPracticeLoopRunV1.created_at.desc(), PaperPracticeLoopRunV1.id.desc())
            .first()
        )
        return str(latest.loop_run_id) if latest is not None else None
    finally:
        session.close()


def _load_decisions(
    settings: Settings,
    *,
    run: str = "latest",
    window_days: int | None = None,
) -> tuple[str, list[PaperPracticeDecisionV1]]:
    resolved_run = _latest_loop_run_id(settings) if run == "latest" else run
    if resolved_run is None:
        return "none", []

    session = get_session(settings)
    try:
        query = session.query(PaperPracticeDecisionV1).filter(
            PaperPracticeDecisionV1.loop_run_id == resolved_run
        )
        if window_days is not None:
            cutoff = utcnow() - timedelta(days=window_days)
            query = query.filter(PaperPracticeDecisionV1.created_at >= cutoff)
        decisions = (
            query.order_by(PaperPracticeDecisionV1.created_at.asc(), PaperPracticeDecisionV1.id.asc())
            .all()
        )
        # Detach rows so callers can safely use them after the session closes.
        for decision in decisions:
            session.expunge(decision)
        return resolved_run, decisions
    finally:
        session.close()


def _write_diagnostic_artifacts(
    settings: Settings,
    *,
    diagnostic_name: str,
    payload: dict[str, Any],
) -> dict[str, str]:
    run_id = str(payload["run_id"])
    artifact_dir = settings.data_dir / "research" / "training" / "diagnostics" / run_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_dir / "summary.json"
    report_path = artifact_dir / "report.qmd"
    state_path = settings.repo_root / ".ai" / "dropbox" / "state" / f"{diagnostic_name}_latest.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)

    report = _render_qmd_report(diagnostic_name=diagnostic_name, payload=payload)
    write_json_artifact(
        summary_path,
        payload,
        owner_type=diagnostic_name,
        owner_key=run_id,
        artifact_type=f"{diagnostic_name}_summary",
        settings=settings,
    )
    write_json_artifact(
        state_path,
        payload,
        owner_type=diagnostic_name,
        owner_key=run_id,
        artifact_type=f"{diagnostic_name}_latest",
        settings=settings,
    )
    write_text_artifact(
        report_path,
        report,
        owner_type=diagnostic_name,
        owner_key=run_id,
        artifact_type=f"{diagnostic_name}_report_qmd",
        artifact_format="qmd",
        settings=settings,
    )
    return {
        "artifact_dir": str(artifact_dir),
        "summary_path": str(summary_path),
        "report_path": str(report_path),
        "state_path": str(state_path),
    }


def _render_qmd_report(*, diagnostic_name: str, payload: dict[str, Any]) -> str:
    top_reasons = payload.get("top_reason_codes", [])
    reason_lines = [
        f"- `{item.get('reason_code')}`: {item.get('count')}"
        for item in top_reasons[:10]
        if isinstance(item, dict)
    ]
    if not reason_lines:
        reason_lines = ["- none"]
    return "\n".join(
        [
            f"# {diagnostic_name.replace('_', ' ').title()}",
            "",
            f"- run id: `{payload.get('run_id')}`",
            f"- status: `{payload.get('status')}`",
            f"- primary failure surface: `{payload.get('primary_failure_surface', 'n/a')}`",
            f"- recommended next action: {payload.get('recommended_next_action', 'n/a')}",
            "",
            "## Top Reason Codes",
            *reason_lines,
            "",
        ]
    )


def diagnose_training_window(settings: Settings, *, regimen: str) -> dict[str, Any]:
    """Summarize historical SQL and feature coverage for a training regimen."""
    profile = get_training_profile(regimen, available_history_days=0) if regimen == "auto" else get_training_profile(regimen)

    session = get_session(settings)
    try:
        sql_days_present = int(
            session.query(func.count(distinct(MarketCandle.event_date_utc)))
            .filter(MarketCandle.event_date_utc.isnot(None))
            .scalar()
            or 0
        )
        feature_days_present = int(
            session.query(func.count(distinct(FeatureGlobalRegimeInput15mV1.event_date_utc)))
            .filter(FeatureGlobalRegimeInput15mV1.event_date_utc.isnot(None))
            .scalar()
            or 0
        )
        sql_min_date = session.query(func.min(MarketCandle.event_date_utc)).scalar()
        sql_max_date = session.query(func.max(MarketCandle.event_date_utc)).scalar()
        feature_min_date = session.query(func.min(FeatureGlobalRegimeInput15mV1.event_date_utc)).scalar()
        feature_max_date = session.query(func.max(FeatureGlobalRegimeInput15mV1.event_date_utc)).scalar()
        observed_sql_dates = {
            str(row[0])
            for row in session.query(distinct(MarketCandle.event_date_utc))
            .filter(MarketCandle.event_date_utc.isnot(None))
            .all()
        }
    finally:
        session.close()

    expected_days = profile.history_lookback_days
    missing_days: list[str] = []
    if sql_max_date:
        end = datetime.fromisoformat(str(sql_max_date)).date()
        expected_dates = [
            (end - timedelta(days=offset)).isoformat()
            for offset in range(expected_days)
        ]
        missing_days = [
            day for day in reversed(expected_dates) if day not in observed_sql_dates
        ]

    coverage_pct = round(sql_days_present / max(1, expected_days), 4)
    feature_coverage_pct = round(feature_days_present / max(1, expected_days), 4)
    if sql_days_present < profile.required_history_days:
        status = "degraded"
        primary_failure_surface = "data"
        next_action = "Collect or hydrate more historical market data before evaluating strategy."
    elif feature_days_present < profile.required_history_days:
        status = "degraded"
        primary_failure_surface = "features"
        next_action = "Repair feature materialization gaps before evaluating strategy."
    else:
        status = "ready"
        primary_failure_surface = "none"
        next_action = "Run gate-funnel and no-trade diagnostics before proposing changes."

    run_id = f"training_window_{regimen}_{utcnow().strftime('%Y%m%dT%H%M%SZ')}"
    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "regimen": profile.name,
        "expected_days": expected_days,
        "required_history_days": profile.required_history_days,
        "minimum_training_days": profile.minimum_training_days,
        "minimum_replay_days": profile.minimum_replay_days,
        "sql_days_present": sql_days_present,
        "feature_days_present": feature_days_present,
        "coverage_pct": coverage_pct,
        "feature_coverage_pct": feature_coverage_pct,
        "sql_date_range": {"start": sql_min_date, "end": sql_max_date},
        "feature_date_range": {"start": feature_min_date, "end": feature_max_date},
        "missing_day_count": len(missing_days),
        "missing_days": missing_days[:50],
        "primary_failure_surface": primary_failure_surface,
        "recommended_next_action": next_action,
    }
    payload.update(_write_diagnostic_artifacts(settings, diagnostic_name="diagnose_training_window", payload=payload))
    return payload


def diagnose_gate_funnel(settings: Settings, *, run: str = "latest") -> dict[str, Any]:
    """Summarize how far paper-practice decisions moved through the gate funnel."""
    resolved_run, decisions = _load_decisions(settings, run=run)

    reason_counts: Counter[str] = Counter()
    surface_counts: Counter[str] = Counter()
    no_trade_cycles = 0
    paper_filled_cycles = 0
    valid_conditions = 0
    policy_allowed = 0
    risk_approved = 0
    quote_available = 0

    for decision in decisions:
        if decision.decision_type == "no_trade":
            no_trade_cycles += 1
        if decision.decision_type in {"paper_trade_opened", "paper_trade_closed"}:
            paper_filled_cycles += 1
        if decision.condition_run_id:
            valid_conditions += 1
        if decision.policy_trace_id is not None or decision.decision_type.startswith("paper_trade"):
            policy_allowed += 1
        if decision.risk_verdict_id is not None or decision.decision_type.startswith("paper_trade"):
            risk_approved += 1
        if decision.quote_snapshot_id is not None or decision.decision_type.startswith("paper_trade"):
            quote_available += 1

        decision_surfaces: set[str] = set()
        for reason_code in _load_json_list(decision.reason_codes_json):
            reason_counts[reason_code] += 1
            surface, _ = _reason_surface(reason_code)
            if decision.decision_type == "no_trade":
                decision_surfaces.add(surface)

        for surface in decision_surfaces:
            surface_counts[surface] += 1

    ranked_surfaces = _ranked_surfaces(surface_counts)
    primary_surface = ranked_surfaces[0]["surface"] if ranked_surfaces else "unknown"
    primary_reason = _top_reason_for_surface(reason_counts, surface=primary_surface)
    recommended_next_action = (
        _reason_surface(primary_reason)[1]
        if primary_reason is not None
        else "Seed paper-practice decisions or run the paper loop before diagnosing the funnel."
    )
    cycles = len(decisions)
    payload: dict[str, Any] = {
        "run_id": f"gate_funnel_{resolved_run}_{utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "status": "completed",
        "loop_run_id": resolved_run,
        "cycles": cycles,
        "valid_features": valid_conditions,
        "valid_conditions": valid_conditions,
        "strategy_candidates": max(cycles - surface_counts.get("strategy_candidate_generation", 0), 0),
        "policy_allowed": policy_allowed,
        "risk_approved": risk_approved,
        "quote_available": quote_available,
        "paper_filled": paper_filled_cycles,
        "no_trade_cycles": no_trade_cycles,
        "primary_failure_surface": primary_surface,
        "failure_surfaces": ranked_surfaces,
        "top_reason_codes": _ranked_counts(reason_counts),
        "recommended_next_action": recommended_next_action,
    }
    payload.update(_write_diagnostic_artifacts(settings, diagnostic_name="diagnose_gate_funnel", payload=payload))
    return payload


def diagnose_no_trades(
    settings: Settings,
    *,
    run: str = "latest",
    window: str = "300d",
) -> dict[str, Any]:
    """Explain why a paper/training window produced no or few paper trades."""
    window_days = _parse_window_days(window)
    resolved_run, decisions = _load_decisions(settings, run=run, window_days=window_days)

    reason_counts: Counter[str] = Counter()
    surface_counts: Counter[str] = Counter()
    no_trade_cycles = 0
    paper_trades = 0
    quote_missing = 0
    risk_rejections = 0

    for decision in decisions:
        reasons = _load_json_list(decision.reason_codes_json)
        if decision.decision_type == "no_trade":
            no_trade_cycles += 1
            if decision.quote_snapshot_id is None:
                quote_missing += 1
        if decision.decision_type in {"paper_trade_opened", "paper_trade_closed"}:
            paper_trades += 1

        decision_surfaces: set[str] = set()
        for reason_code in reasons:
            reason_counts[reason_code] += 1
            surface, _ = _reason_surface(reason_code)
            if decision.decision_type == "no_trade":
                decision_surfaces.add(surface)
                if surface == "risk":
                    risk_rejections += 1

        for surface in decision_surfaces:
            surface_counts[surface] += 1

    ranked_surfaces = _ranked_surfaces(surface_counts)
    ranked_reasons = _ranked_counts(reason_counts)
    primary_surface = ranked_surfaces[0]["surface"] if ranked_surfaces else "unknown"
    primary_reason = _top_reason_for_surface(reason_counts, surface=primary_surface)
    if primary_reason is not None:
        recommended_next_action = _reason_surface(primary_reason)[1]
    elif not decisions:
        primary_surface = "data"
        recommended_next_action = "Run or seed a paper-practice loop before diagnosing no-trade behavior."
    else:
        recommended_next_action = "Inspect paper decisions with missing reason codes."

    payload: dict[str, Any] = {
        "run_id": f"no_trades_{resolved_run}_{window_days}d_{utcnow().strftime('%Y%m%dT%H%M%SZ')}",
        "status": "completed",
        "loop_run_id": resolved_run,
        "window_days": window_days,
        "total_decision_cycles": len(decisions),
        "no_trade_cycles": no_trade_cycles,
        "strategy_candidates": max(len(decisions) - surface_counts.get("strategy_candidate_generation", 0), 0),
        "policy_blocks": surface_counts.get("policy", 0),
        "risk_rejections": risk_rejections,
        "quote_missing": quote_missing,
        "paper_trades": paper_trades,
        "primary_failure_surface": primary_surface,
        "failure_surfaces": ranked_surfaces,
        "top_reason_codes": ranked_reasons,
        "recommended_next_action": recommended_next_action,
    }
    payload.update(_write_diagnostic_artifacts(settings, diagnostic_name="diagnose_no_trades", payload=payload))
    return payload
