"""Autonomous paper-practice loop over bounded live-cycle receipts."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any

import orjson
import pandas as pd
from sqlalchemy import desc

from d5_trading_engine.capture.source_collection import BackgroundSourceCollector
from d5_trading_engine.capture.massive_backfill import MassiveMinuteAggsBackfill
from d5_trading_engine.capture.runner import CaptureRunner
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.condition.scorer import ConditionScorer
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.features.materializer import FeatureMaterializer
from d5_trading_engine.paper_runtime.operator import PaperTradeOperator
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.proposals import create_improvement_proposal
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata
from d5_trading_engine.research_loop.live_regime_cycle import LiveRegimeCycleRunner
from d5_trading_engine.research_loop.proposal_comparison import ProposalComparator
from d5_trading_engine.research_loop.proposal_review import ProposalReviewer
from d5_trading_engine.research_loop.regime_model_compare import RegimeModelComparator
from d5_trading_engine.research_loop.training_events import append_training_event_safe
from d5_trading_engine.settlement.backtest import BacktestTruthOwner
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    MarketCandle,
    PaperPracticeDecisionV1,
    PaperPracticeLoopRunV1,
    PaperPracticeProfileRevisionV1,
    PaperPracticeProfileV1,
    PaperPosition,
    PaperSession,
    PaperSessionReport,
    QuoteSnapshot,
    TokenMetadataSnapshot,
    TokenRegistry,
)

_DEFAULT_STRATEGY_REPORT = (
    Path(".ai") / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json"
)
_ALLOWED_PROFILE_KEYS = (
    "preferred_family",
    "strategy_report_path",
    "minimum_condition_confidence",
    "stop_loss_bps",
    "take_profit_bps",
    "time_stop_bars",
    "cooldown_bars",
)


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = orjson.loads(path.read_bytes())
    except FileNotFoundError:
        return {}
    except orjson.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _as_utc_timestamp(value) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


class PaperPracticeRuntime:
    """Own the bounded autonomous paper-practice loop and profile overlay."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def historical_cache_status(self) -> dict[str, Any]:
        backfill = MassiveMinuteAggsBackfill(self.settings, runner=CaptureRunner(self.settings))
        return backfill.historical_cache_status()

    def hydrate_history(self, *, max_days: int | None = None) -> dict[str, Any]:
        backfill = MassiveMinuteAggsBackfill(self.settings, runner=CaptureRunner(self.settings))
        return asyncio.run(backfill.backfill_missing_full_free_tier(max_days=max_days, resume=True))

    def run_source_collection(
        self,
        *,
        max_massive_days: int = 1,
        include_helius: bool = False,
        include_jupiter: bool = True,
    ) -> dict[str, Any]:
        collector = BackgroundSourceCollector(self.settings)
        return asyncio.run(
            collector.collect_incremental(
                max_massive_days=max_massive_days,
                include_helius=include_helius,
                include_jupiter=include_jupiter,
            )
        )

    def run_bootstrap(self) -> dict[str, Any]:
        profile = self.ensure_active_profile()
        bootstrap_id = f"paper_practice_bootstrap_{uuid.uuid4().hex[:12]}"
        artifact_dir = (
            self.settings.data_dir / "research" / "paper_practice" / "bootstrap" / bootstrap_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        end_date = utcnow().date() - timedelta(days=1)
        start_date = end_date - timedelta(days=self.settings.massive_free_tier_lookback_days - 1)

        backfill = MassiveMinuteAggsBackfill(self.settings, runner=CaptureRunner(self.settings))
        materializer = FeatureMaterializer(self.settings)
        comparator = RegimeModelComparator(self.settings)

        backfill_result = asyncio.run(backfill.backfill_missing_full_free_tier(resume=True))
        feature_run_id, feature_rows = materializer.materialize_global_regime_inputs_15m_v1()
        comparison_result = comparator.run_regime_model_compare_v1(
            history_start=start_date.isoformat(),
            history_end=end_date.isoformat(),
            use_massive_context=True,
        )
        backtest_result = self.run_backtest_walk_forward()

        payload = {
            "bootstrap_id": bootstrap_id,
            "profile_id": profile["profile_id"],
            "active_revision_id": profile["active_revision_id"],
            "history_start": start_date.isoformat(),
            "history_end": end_date.isoformat(),
            "backfill_result": backfill_result,
            "feature_run_id": feature_run_id,
            "feature_rows": feature_rows,
            "comparison_result": comparison_result,
            "backtest_result": backtest_result,
            "artifact_dir": str(artifact_dir),
            "completed_ladder": bool(backtest_result["completed_ladder"]),
            "next_command": "d5 run-paper-practice-loop --max-iterations 1 --json",
        }
        write_json_artifact(
            artifact_dir / "bootstrap_summary.json",
            payload,
            owner_type="paper_practice_bootstrap",
            owner_key=bootstrap_id,
            artifact_type="paper_practice_bootstrap_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "experiment_run.qmd",
                title="paper practice bootstrap",
                metadata=trading_report_metadata(
                    report_kind="paper_practice_bootstrap",
                    run_id=bootstrap_id,
                    owner_type="paper_practice_bootstrap",
                    owner_key=bootstrap_id,
                    profile_revision_id=profile["active_revision_id"],
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="15m",
                    summary_path="bootstrap_summary.json",
                    config_path="config.json",
                ),
                summary_lines=[
                    f"- bootstrap id: `{bootstrap_id}`",
                    f"- profile id: `{profile['profile_id']}`",
                    f"- history start: `{start_date.isoformat()}`",
                    f"- history end: `{end_date.isoformat()}`",
                    f"- feature rows: `{feature_rows}`",
                    f"- comparison run id: `{comparison_result['run_id']}`",
                ],
                sections=[
                    (
                        "Market / Source Context",
                        [
                            f"- batch id: `{backfill_result['batch_id']}`",
                            f"- captured days: `{backfill_result['days']['captured_count']}`",
                            f"- skipped days: `{backfill_result['days']['skipped_count']}`",
                            "- warehouse contract: raw `CSV.gz` + partitioned `Parquet` + normalized `SQL`",
                        ],
                    ),
                    (
                        "Regime / Condition / Policy / Risk",
                        [
                            f"- recommended candidate: `{comparison_result['recommended_candidate']}`",
                            f"- proposal status: `{comparison_result['proposal_status']}`",
                        ],
                    ),
                    (
                        "Trade / Replay Outcome",
                        [
                            f"- backtest run id: `{backtest_result['run_id']}`",
                            f"- windows completed: `{backtest_result['window_count']}`",
                            f"- completed ladder: `{backtest_result['completed_ladder']}`",
                            f"- active revision: `{backtest_result['active_revision_id']}`",
                        ],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="paper_practice_bootstrap",
            owner_key=bootstrap_id,
            artifact_type="paper_practice_bootstrap_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        self._write_status_receipts(
            profile=profile,
            latest_trade_receipt={},
            loop_state={
                "status": "bootstrap_completed",
                "bootstrap_id": bootstrap_id,
                "feature_run_id": feature_run_id,
                "comparison_run_id": comparison_result["run_id"],
                "backtest_run_id": backtest_result["run_id"],
                "backtest_window_count": backtest_result["window_count"],
                "historical_ladder_completed": bool(backtest_result["completed_ladder"]),
            },
        )
        return payload

    def historical_cache_status(self) -> dict[str, Any]:
        """Return the bounded Massive historical cache status."""
        return MassiveMinuteAggsBackfill(
            self.settings,
            runner=CaptureRunner(self.settings),
        ).historical_cache_status()

    def hydrate_history(self, *, max_days: int | None = None) -> dict[str, Any]:
        """Fill only the missing portion of the bounded Massive historical cache."""
        backfill = MassiveMinuteAggsBackfill(self.settings, runner=CaptureRunner(self.settings))
        return asyncio.run(
            backfill.backfill_missing_full_free_tier(
                max_days=max_days,
                resume=True,
            )
        )

    def run_source_collection(
        self,
        *,
        max_massive_days: int = 1,
        include_helius: bool = False,
        include_jupiter: bool = True,
    ) -> dict[str, Any]:
        """Run one bounded incremental collection pass against stored truth."""
        return asyncio.run(
            BackgroundSourceCollector(self.settings).collect_incremental(
                max_massive_days=max_massive_days,
                include_helius=include_helius,
                include_jupiter=include_jupiter,
            )
        )

    def run_backtest_walk_forward(self) -> dict[str, Any]:
        profile = self.ensure_active_profile()
        starting_revision_id = profile["active_revision_id"]
        run_id = f"backtest_walk_forward_{uuid.uuid4().hex[:12]}"
        artifact_dir = (
            self.settings.data_dir / "research" / "paper_practice" / "backtests" / run_id
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)

        scorer = ConditionScorer(self.settings)
        comparator = RegimeModelComparator(self.settings)
        feature_run = scorer._latest_feature_run()
        history = scorer._load_feature_history(feature_run.run_id).sort_values(
            "bucket_start_utc"
        )
        if history.empty:
            raise RuntimeError(
                "No global regime input rows available for walk-forward replay. "
                "Run `d5 materialize-features global-regime-inputs-15m-v1` first."
            )

        history_start = _as_utc_timestamp(history["bucket_start_utc"].min())
        history_end = _as_utc_timestamp(history["bucket_start_utc"].max())
        training_end = history_start + pd.DateOffset(years=1)
        replay_history = history.loc[history["bucket_start_utc"] >= training_end].copy()
        if replay_history.empty:
            raise RuntimeError(
                "Need at least one 3-month replay window after the first 12 calendar months. "
                "Refresh the historical ladder, then rerun `d5 run-paper-practice-bootstrap`."
            )

        macro_context_state = scorer._macro_context_state(feature_run)
        price_history = self._load_backtest_price_history()
        window_results: list[dict[str, Any]] = []

        window_start = _as_utc_timestamp(replay_history["bucket_start_utc"].min())
        while window_start <= history_end:
            next_window_start = _as_utc_timestamp(window_start + pd.DateOffset(months=3))
            window_end_exclusive = min(next_window_start, history_end + pd.Timedelta(microseconds=1))
            expanding_history = history.loc[
                history["bucket_start_utc"] < window_end_exclusive
            ].copy()
            scored_history, _, _ = scorer._build_walk_forward_history_frame(
                expanding_history,
                macro_context_state=macro_context_state,
            )
            window_frame = scored_history.loc[
                (scored_history["bucket_start_utc"] >= window_start)
                & (scored_history["bucket_start_utc"] < window_end_exclusive)
            ].copy()
            if window_frame.empty:
                window_start = next_window_start
                continue

            comparison_result = comparator.run_regime_model_compare_v1(
                history_start=history_start.date().isoformat(),
                history_end=(
                    _as_utc_timestamp(window_frame["bucket_start_utc"].max())
                    .date()
                    .isoformat()
                ),
                use_massive_context=True,
            )
            profile = self.ensure_active_profile()
            window_result = self._run_backtest_window(
                run_id=run_id,
                window_index=len(window_results) + 1,
                profile=profile,
                window_frame=window_frame,
                price_history=price_history,
                comparison_result=comparison_result,
            )
            window_results.append(window_result)
            window_start = next_window_start

        active_profile = self.ensure_active_profile()
        payload = {
            "run_id": run_id,
            "status": "completed",
            "completed_ladder": bool(window_results),
            "feature_run_id": feature_run.run_id,
            "history_start": history_start.date().isoformat(),
            "history_end": history_end.date().isoformat(),
            "training_end": _as_utc_timestamp(training_end).date().isoformat(),
            "window_count": len(window_results),
            "starting_revision_id": starting_revision_id,
            "active_profile_id": active_profile["profile_id"],
            "active_revision_id": active_profile["active_revision_id"],
            "window_results": window_results,
            "artifact_dir": str(artifact_dir),
            "next_command": "d5 run-paper-practice-loop --max-iterations 1 --json",
        }
        write_json_artifact(
            artifact_dir / "summary.json",
            payload,
            owner_type="paper_practice_backtest",
            owner_key=run_id,
            artifact_type="paper_practice_backtest_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "experiment_run.qmd",
                title="paper practice backtest walk-forward",
                metadata=trading_report_metadata(
                    report_kind="paper_practice_backtest",
                    run_id=run_id,
                    owner_type="paper_practice_backtest",
                    owner_key=run_id,
                    profile_revision_id=active_profile["active_revision_id"],
                    instrument_scope=["SOL/USDC"],
                    context_instruments=list(self.settings.coinbase_context_symbols),
                    timeframe="15m",
                    summary_path="summary.json",
                    config_path="summary.json",
                ),
                summary_lines=[
                    f"- run id: `{run_id}`",
                    f"- feature run id: `{feature_run.run_id}`",
                    f"- history start: `{payload['history_start']}`",
                    f"- history end: `{payload['history_end']}`",
                    f"- training end: `{payload['training_end']}`",
                    f"- windows completed: `{len(window_results)}`",
                    f"- active revision: `{active_profile['active_revision_id']}`",
                ],
                sections=[
                    (
                        "Trade / Replay Outcome",
                        [
                            (
                                f"- `{item['window_label']}` session=`{item['session_key']}` "
                                f"close_reason=`{item['close_reason']}` "
                                f"realized_pnl_usdc=`{item['realized_pnl_usdc']}` "
                                f"proposal_applied=`{item['proposal_applied']}`"
                            )
                            for item in window_results
                        ]
                        or ["- no replay windows completed"],
                    ),
                    (
                        "Bounded Next Change",
                        [
                            "- auto-apply only bounded paper-profile adjustments that beat the latest accepted baseline",
                            f"- active revision after replay: `{active_profile['active_revision_id']}`",
                        ],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="paper_practice_backtest",
            owner_key=run_id,
            artifact_type="paper_practice_backtest_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        append_training_event_safe(
            self.settings,
            event_type="experiment_completed",
            summary="Adaptive walk-forward replay completed for the bounded paper-practice ladder.",
            owner_kind="paper_practice_backtest",
            run_id=run_id,
            qmd_reports=[artifact_dir / "report.qmd"],
            sql_refs=[f"paper_practice_backtest:{run_id}"],
            context_files=[
                Path("src/d5_trading_engine/paper_runtime/practice.py"),
                Path("src/d5_trading_engine/settlement/backtest.py"),
            ],
            notes=(
                "Compare the latest replay window set against the accepted baseline and "
                "keep, revert, or shadow one bounded paper-profile change."
            ),
        )
        return payload

    def _ensure_historical_ladder_completed(self) -> dict[str, Any]:
        status_path = (
            self.settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "paper_practice_status.json"
        )
        if status_path.exists():
            payload = _load_json_file(status_path)
            loop_state = payload.get("loop_state") if isinstance(payload, dict) else {}
            if isinstance(loop_state, dict) and loop_state.get("historical_ladder_completed"):
                return payload

        bootstrap_root = self.settings.data_dir / "research" / "paper_practice" / "bootstrap"
        summary_paths = sorted(
            bootstrap_root.glob("*/bootstrap_summary.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in summary_paths:
            payload = _load_json_file(path)
            if bool((payload.get("backtest_result") or {}).get("completed_ladder")):
                return payload

        raise RuntimeError(
            "Historical paper-practice ladder is incomplete. "
            "Run `d5 run-paper-practice-bootstrap` first."
        )

    def run_loop(
        self,
        *,
        with_helius_ws: bool = False,
        max_iterations: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_historical_ladder_completed()
        profile = self.ensure_active_profile()
        loop_run_id = f"paper_practice_loop_{uuid.uuid4().hex[:12]}"
        started_at = utcnow()
        session = get_session(self.settings)
        try:
            session.add(
                PaperPracticeLoopRunV1(
                    loop_run_id=loop_run_id,
                    mode="continuous_practice",
                    status="running",
                    active_profile_id=profile["profile_id"],
                    active_revision_id=profile["active_revision_id"],
                    with_helius_ws=1 if with_helius_ws else 0,
                    max_iterations=max_iterations,
                    iterations_completed=0,
                    latest_decision_id=None,
                    latest_session_key="",
                    last_cycle_id="",
                    started_at=started_at,
                    finished_at=None,
                    created_at=started_at,
                )
            )
            session.commit()
        finally:
            session.close()

        iterations_completed = 0
        latest_trade_receipt: dict[str, Any] = {}
        try:
            while True:
                iteration_result = self._run_iteration(
                    loop_run_id=loop_run_id,
                    with_helius_ws=with_helius_ws,
                )
                iterations_completed += 1
                latest_trade_receipt = iteration_result.get("latest_trade_receipt", {})
                self._update_loop_run(
                    loop_run_id=loop_run_id,
                    status="running",
                    iterations_completed=iterations_completed,
                    latest_decision_id=iteration_result["latest_decision_id"],
                    latest_session_key=iteration_result.get("latest_session_key", ""),
                    last_cycle_id=iteration_result.get("cycle_id", ""),
                )

                profile = self.ensure_active_profile()
                self._write_status_receipts(
                    profile=profile,
                    latest_trade_receipt=latest_trade_receipt,
                    loop_state={
                        "loop_run_id": loop_run_id,
                        "status": "running",
                        "iterations_completed": iterations_completed,
                        "latest_decision_id": iteration_result["latest_decision_id"],
                        "latest_session_key": iteration_result.get("latest_session_key", ""),
                        "last_cycle_id": iteration_result.get("cycle_id", ""),
                    },
                )
                if max_iterations is not None and iterations_completed >= max_iterations:
                    break

                sleep_seconds = max(60, int(profile["payload"]["cadence_minutes"] * 60))
                time.sleep(sleep_seconds)

            finished_at = utcnow()
            self._update_loop_run(
                loop_run_id=loop_run_id,
                status="completed",
                iterations_completed=iterations_completed,
                latest_decision_id=None,
                latest_session_key=None,
                last_cycle_id=None,
                finished_at=finished_at,
            )
            return {
                "loop_run_id": loop_run_id,
                "status": "completed",
                "iterations_completed": iterations_completed,
                "active_profile_id": profile["profile_id"],
                "active_revision_id": profile["active_revision_id"],
                "latest_trade_receipt": latest_trade_receipt,
            }
        except Exception:
            self._update_loop_run(
                loop_run_id=loop_run_id,
                status="failed",
                iterations_completed=iterations_completed,
                latest_decision_id=None,
                latest_session_key=None,
                last_cycle_id=None,
                finished_at=utcnow(),
            )
            raise

    def get_status(self) -> dict[str, Any]:
        profile = self.ensure_active_profile()
        session = get_session(self.settings)
        try:
            latest_loop = (
                session.query(PaperPracticeLoopRunV1)
                .order_by(
                    desc(PaperPracticeLoopRunV1.started_at),
                    desc(PaperPracticeLoopRunV1.id),
                )
                .first()
            )
            open_session = self._select_open_session(session)
            latest_decision = None
            if latest_loop is not None and latest_loop.latest_decision_id:
                latest_decision = (
                    session.query(PaperPracticeDecisionV1)
                    .filter_by(decision_id=latest_loop.latest_decision_id)
                    .first()
                )
            return {
                "active_profile_id": profile["profile_id"],
                "active_revision_id": profile["active_revision_id"],
                "profile_payload": profile["payload"],
                "open_session_key": open_session.session_key if open_session else "",
                "open_session_status": open_session.status if open_session else "",
                "latest_loop_run_id": latest_loop.loop_run_id if latest_loop else "",
                "latest_loop_status": latest_loop.status if latest_loop else "",
                "latest_decision_id": latest_decision.decision_id if latest_decision else "",
                "latest_decision_type": latest_decision.decision_type if latest_decision else "",
            }
        finally:
            session.close()

    def ensure_active_profile(self) -> dict[str, Any]:
        session = get_session(self.settings)
        try:
            profile_row = (
                session.query(PaperPracticeProfileV1)
                .filter_by(status="active")
                .order_by(desc(PaperPracticeProfileV1.updated_at), desc(PaperPracticeProfileV1.id))
                .first()
            )
            if profile_row is None:
                created_at = utcnow()
                profile_id = f"paper_profile_{uuid.uuid4().hex[:12]}"
                revision_id = f"paper_profile_revision_{uuid.uuid4().hex[:12]}"
                payload = self._default_profile_payload()
                profile_row = PaperPracticeProfileV1(
                    profile_id=profile_id,
                    status="active",
                    active_revision_id=revision_id,
                    instrument_pair=payload["instrument_pair"],
                    context_anchors_json=orjson.dumps(payload["context_anchors"]).decode(),
                    cadence_minutes=int(payload["cadence_minutes"]),
                    max_open_sessions=int(payload["max_open_sessions"]),
                    created_at=created_at,
                    updated_at=created_at,
                )
                session.add(profile_row)
                session.flush()
                session.add(
                    PaperPracticeProfileRevisionV1(
                        revision_id=revision_id,
                        profile_id=profile_id,
                        revision_index=1,
                        status="active",
                        mutation_source="bootstrap",
                        source_proposal_id=None,
                        source_review_id=None,
                        source_comparison_id=None,
                        applied_parameter_json=orjson.dumps(payload).decode(),
                        allowed_mutation_keys_json=orjson.dumps(list(_ALLOWED_PROFILE_KEYS)).decode(),
                        summary="Created the initial active paper-only practice profile.",
                        created_at=created_at,
                    )
                )
                session.commit()
                self._write_profile_revision_artifacts(
                    profile_id=profile_id,
                    revision_id=revision_id,
                    payload=payload,
                    summary="Created the initial active paper-only practice profile.",
                    mutation_source="bootstrap",
                )
            revision_row = (
                session.query(PaperPracticeProfileRevisionV1)
                .filter_by(revision_id=profile_row.active_revision_id)
                .one()
            )
            payload = orjson.loads(revision_row.applied_parameter_json)
            serialized = {
                "profile_id": profile_row.profile_id,
                "active_revision_id": revision_row.revision_id,
                "payload": payload,
            }
        finally:
            session.close()

        self._write_profile_receipt(serialized, mutation_source="active_profile_refresh")
        return serialized

    def _run_iteration(
        self,
        *,
        loop_run_id: str,
        with_helius_ws: bool,
    ) -> dict[str, Any]:
        profile = self.ensure_active_profile()
        cycle_result = asyncio.run(
            LiveRegimeCycleRunner(self.settings).run_live_regime_cycle(
                with_helius_ws=with_helius_ws
            )
        )
        session = get_session(self.settings)
        try:
            current_condition = (
                session.query(ConditionGlobalRegimeSnapshotV1)
                .filter_by(condition_run_id=cycle_result["condition_run_id"])
                .order_by(desc(ConditionGlobalRegimeSnapshotV1.created_at))
                .first()
            )
            open_session = self._select_open_session(session)
        finally:
            session.close()

        if open_session is not None:
            return self._handle_open_session_iteration(
                loop_run_id=loop_run_id,
                profile=profile,
                cycle_result=cycle_result,
                current_condition=current_condition,
                open_session_key=open_session.session_key,
            )

        return self._handle_entry_iteration(
            loop_run_id=loop_run_id,
            profile=profile,
            cycle_result=cycle_result,
            current_condition=current_condition,
        )

    def _run_backtest_window(
        self,
        *,
        run_id: str,
        window_index: int,
        profile: dict[str, Any],
        window_frame: pd.DataFrame,
        price_history: pd.DataFrame,
        comparison_result: dict[str, Any],
    ) -> dict[str, Any]:
        payload = profile["payload"]
        strategy_selection = self._load_profile_strategy_selection(payload)
        sol_mint = self._mint_for_symbol("SOL")
        owner = BacktestTruthOwner(self.settings)
        window_start = _as_utc_timestamp(window_frame["bucket_start_utc"].min())
        window_end = _as_utc_timestamp(window_frame["bucket_start_utc"].max())
        session_key = f"{run_id}_window_{window_index:02d}_{uuid.uuid4().hex[:8]}"
        window_label = (
            f"{window_start.date().isoformat()}..{window_end.date().isoformat()}"
        )
        opened = owner.open_spot_session(
            session_key=session_key,
            bucket_granularity="15m",
            fee_bps=10,
            slippage_bps=15,
            latency_ms=0,
            starting_cash_usdc=100.0,
            mark_method="replay_last_fill",
            metadata={
                "window_index": window_index,
                "window_label": window_label,
                "profile_id": profile["profile_id"],
                "profile_revision_id": profile["active_revision_id"],
                "comparison_run_id": comparison_result["run_id"],
                "strategy_top_family": strategy_selection["top_family"],
            },
            opened_at=window_start.to_pydatetime(),
        )

        position_state: dict[str, Any] | None = None
        latest_close_reason = ""
        latest_exit_metrics: dict[str, Any] = {}
        last_cash_usdc = float(opened["starting_cash_usdc"])

        for row in window_frame.itertuples(index=False):
            bucket_time = _as_utc_timestamp(row.bucket_start_utc)
            price_usdc = self._lookup_backtest_price(price_history, bucket_time)
            if position_state is None:
                if self._historical_entry_blocked(
                    profile_payload=payload,
                    strategy_selection=strategy_selection,
                    semantic_regime=str(row.semantic_regime or ""),
                    confidence=float(row.confidence or 0.0),
                ):
                    continue
                quote_size_usdc = min(last_cash_usdc, 10.0)
                if quote_size_usdc <= 0:
                    continue
                quantity_tokens = quote_size_usdc / price_usdc
                quantity_lamports = int(round(quantity_tokens * (10**9)))
                if quantity_lamports <= 0:
                    continue
                fill = owner.record_fill(
                    session_id=int(opened["session_id"]),
                    event_time=bucket_time.to_pydatetime(),
                    mint=sol_mint,
                    side="buy",
                    input_amount=str(int(round(quote_size_usdc * (10**6)))),
                    output_amount=str(quantity_lamports),
                    fill_price_usdc=float(price_usdc),
                    replay_reference=f"bucket:{bucket_time.isoformat()}",
                    reason_codes=[
                        "historical_replay_entry",
                        f"strategy_family:{strategy_selection['top_family']}",
                    ],
                )
                last_cash_usdc = float(fill["cash_usdc"])
                position_state = {
                    "entry_price_usdc": float(price_usdc),
                    "entry_cost_usdc": quote_size_usdc,
                    "quantity_lamports": quantity_lamports,
                    "entry_bucket_time": bucket_time,
                }
                continue

            quantity_tokens = float(position_state["quantity_lamports"]) / (10**9)
            pnl_usdc = (quantity_tokens * price_usdc) - float(position_state["entry_cost_usdc"])
            pnl_bps = (
                (pnl_usdc / float(position_state["entry_cost_usdc"])) * 10_000.0
                if float(position_state["entry_cost_usdc"]) > 0
                else 0.0
            )
            bars_held = int(
                max(
                    0,
                    (bucket_time - _as_utc_timestamp(position_state["entry_bucket_time"])).total_seconds()
                    // max(60, int(payload["cadence_minutes"]) * 60),
                )
            )
            close_reason = self._historical_exit_reason(
                profile_payload=payload,
                semantic_regime=str(row.semantic_regime or ""),
                pnl_usdc=pnl_usdc,
                pnl_bps=pnl_bps,
                bars_held=bars_held,
            )
            if close_reason is None:
                continue

            latest_close_reason = close_reason
            latest_exit_metrics = {
                "pnl_usdc": pnl_usdc,
                "pnl_bps": pnl_bps,
                "bars_held": bars_held,
                "semantic_regime": str(row.semantic_regime or ""),
                "window_label": window_label,
            }
            sell = owner.record_fill(
                session_id=int(opened["session_id"]),
                event_time=bucket_time.to_pydatetime(),
                mint=sol_mint,
                side="sell",
                input_amount=str(int(position_state["quantity_lamports"])),
                output_amount=str(int(round(quantity_tokens * price_usdc * (10**6)))),
                fill_price_usdc=float(price_usdc),
                replay_reference=f"bucket:{bucket_time.isoformat()}",
                reason_codes=[f"close_reason:{close_reason}"],
            )
            last_cash_usdc = float(sell["cash_usdc"])
            position_state = None

        if position_state is not None:
            final_bucket = _as_utc_timestamp(window_frame["bucket_start_utc"].max())
            final_price = self._lookup_backtest_price(price_history, final_bucket)
            quantity_tokens = float(position_state["quantity_lamports"]) / (10**9)
            latest_close_reason = "window_end"
            latest_exit_metrics = {
                "pnl_usdc": (quantity_tokens * final_price)
                - float(position_state["entry_cost_usdc"]),
                "pnl_bps": (
                    (
                        ((quantity_tokens * final_price) - float(position_state["entry_cost_usdc"]))
                        / float(position_state["entry_cost_usdc"])
                    )
                    * 10_000.0
                    if float(position_state["entry_cost_usdc"]) > 0
                    else 0.0
                ),
                "bars_held": int(
                    max(
                        0,
                        (final_bucket - _as_utc_timestamp(position_state["entry_bucket_time"])).total_seconds()
                        // max(60, int(payload["cadence_minutes"]) * 60),
                    )
                ),
                "semantic_regime": str(window_frame.iloc[-1]["semantic_regime"] or ""),
                "window_label": window_label,
            }
            sell = owner.record_fill(
                session_id=int(opened["session_id"]),
                event_time=final_bucket.to_pydatetime(),
                mint=sol_mint,
                side="sell",
                input_amount=str(int(position_state["quantity_lamports"])),
                output_amount=str(int(round(quantity_tokens * final_price * (10**6)))),
                fill_price_usdc=float(final_price),
                replay_reference=f"bucket:{final_bucket.isoformat()}",
                reason_codes=["close_reason:window_end"],
            )
            last_cash_usdc = float(sell["cash_usdc"])

        close_result = owner.close_session(
            session_id=int(opened["session_id"]),
            closed_at=window_end.to_pydatetime(),
            reason_codes=[f"close_reason:{latest_close_reason or 'window_end'}"],
        )
        proposal_result = self._review_and_apply_backtest_window(
            profile=profile,
            session_key=session_key,
            close_reason=latest_close_reason or "window_end",
            exit_metrics=latest_exit_metrics
            or {
                "pnl_usdc": float(close_result["realized_pnl_usdc"] or 0.0),
                "pnl_bps": 0.0,
                "bars_held": 0.0,
                "semantic_regime": str(window_frame.iloc[-1]["semantic_regime"] or ""),
                "window_label": window_label,
            },
        )

        artifact_dir = self.settings.data_dir / "research" / "paper_practice" / "backtests" / run_id
        window_payload = {
            "run_id": run_id,
            "window_index": window_index,
            "window_label": window_label,
            "session_key": session_key,
            "close_reason": latest_close_reason or "window_end",
            "realized_pnl_usdc": float(close_result["realized_pnl_usdc"] or 0.0),
            "ending_cash_usdc": float(close_result["cash_usdc"] or last_cash_usdc),
            "comparison_run_id": comparison_result["run_id"],
            "profile_id": profile["profile_id"],
            "starting_revision_id": profile["active_revision_id"],
            "proposal_id": proposal_result.get("proposal_id", ""),
            "proposal_applied": bool(proposal_result.get("applied")),
        }
        write_json_artifact(
            artifact_dir / f"window_{window_index:02d}.json",
            window_payload,
            owner_type="backtest_session",
            owner_key=session_key,
            artifact_type="backtest_window_summary",
            settings=self.settings,
        )
        return window_payload

    def _handle_entry_iteration(
        self,
        *,
        loop_run_id: str,
        profile: dict[str, Any],
        cycle_result: dict[str, Any],
        current_condition: ConditionGlobalRegimeSnapshotV1 | None,
    ) -> dict[str, Any]:
        payload = profile["payload"]
        reason_codes: list[str] = []
        if not cycle_result["ready_for_paper_cycle"]:
            reason_codes.append("paper_ready_receipt_not_actionable")
        semantic_regime = getattr(current_condition, "semantic_regime", "")
        confidence = float(getattr(current_condition, "confidence", 0.0) or 0.0)
        if semantic_regime not in set(payload["regime_allowlist"]):
            reason_codes.append(f"regime_not_allowed:{semantic_regime or 'unknown'}")
        if confidence < float(payload["minimum_condition_confidence"]):
            reason_codes.append("condition_confidence_below_profile_minimum")
        if self._cooldown_active(int(payload["cooldown_bars"]), int(payload["cadence_minutes"])):
            reason_codes.append("profile_cooldown_active")
        strategy_selection: dict[str, Any] | None = None
        if not reason_codes:
            try:
                strategy_selection = self._load_profile_strategy_selection(payload)
            except Exception as exc:  # pragma: no cover - surfaced as a reason code
                reason_codes.append(
                    f"strategy_selection_unavailable:{type(exc).__name__}"
                )
        if strategy_selection is not None:
            target_label = str(strategy_selection.get("target_label") or "")
            allowed_regimes = {
                str(item) for item in (strategy_selection.get("allowed_regimes") or [])
            }
            if target_label != "up":
                reason_codes.append(
                    f"strategy_target_not_runtime_long:{target_label or 'unknown'}"
                )
            if semantic_regime not in allowed_regimes:
                reason_codes.append(f"strategy_regime_not_allowed:{semantic_regime or 'unknown'}")

        decision_type = "no_trade"
        latest_trade_receipt: dict[str, Any] = {}
        latest_session_key = ""
        policy_trace_id: int | None = None
        risk_verdict_id: int | None = None
        if not reason_codes:
            operator = PaperTradeOperator(self.settings)
            strategy_report_path = Path(payload["strategy_report_path"])
            result = operator.run_cycle(
                quote_snapshot_id=int(cycle_result["quote_snapshot_id"]),
                condition_run_id=str(cycle_result["condition_run_id"]),
                strategy_report_path=strategy_report_path,
                preferred_family=(payload.get("preferred_family") or None),
            )
            decision_type = "paper_trade_opened"
            raw_policy_trace_id = result["policy_result"].get("trace_id")
            raw_risk_verdict_id = result["risk_result"].get("risk_verdict_id")
            policy_trace_id = (
                int(raw_policy_trace_id) if raw_policy_trace_id is not None else None
            )
            risk_verdict_id = (
                int(raw_risk_verdict_id) if raw_risk_verdict_id is not None else None
            )
            latest_trade_receipt = {
                "decision_type": decision_type,
                "session_key": result["session_key"],
                "quote_snapshot_id": int(cycle_result["quote_snapshot_id"]),
                "condition_run_id": str(cycle_result["condition_run_id"]),
                "policy_state": result["policy_result"]["policy_state"],
                "risk_state": result["risk_result"]["risk_state"],
                "strategy_report_path": str(strategy_report_path),
                "preferred_family": payload.get("preferred_family") or "",
                "strategy_target_label": strategy_selection["target_label"]
                if strategy_selection is not None
                else "",
                "timestamp": utcnow().isoformat(),
            }
            latest_session_key = result["session_key"]

        decision = self._record_decision(
            loop_run_id=loop_run_id,
            profile=profile,
            decision_type=decision_type,
            session_key=latest_session_key,
            quote_snapshot_id=int(cycle_result["quote_snapshot_id"]) if cycle_result["quote_snapshot_id"] else None,
            condition_run_id=str(cycle_result["condition_run_id"]),
            policy_trace_id=policy_trace_id,
            risk_verdict_id=risk_verdict_id,
            decision_payload={
                "cycle_id": cycle_result["cycle_id"],
                "semantic_regime": semantic_regime,
                "condition_confidence": confidence,
                "paper_ready": bool(cycle_result["ready_for_paper_cycle"]),
                "latest_trade_receipt": latest_trade_receipt,
            },
            reason_codes=reason_codes or ["paper_trade_opened"],
        )
        if latest_trade_receipt:
            self._write_trade_receipt(latest_trade_receipt)
        return {
            "latest_decision_id": decision["decision_id"],
            "latest_session_key": latest_session_key,
            "cycle_id": cycle_result["cycle_id"],
            "latest_trade_receipt": latest_trade_receipt,
        }

    def _handle_open_session_iteration(
        self,
        *,
        loop_run_id: str,
        profile: dict[str, Any],
        cycle_result: dict[str, Any],
        current_condition: ConditionGlobalRegimeSnapshotV1 | None,
        open_session_key: str,
    ) -> dict[str, Any]:
        payload = profile["payload"]
        exit_quote = self._capture_close_quote(open_session_key=open_session_key)
        exit_reason, exit_metrics = self._evaluate_exit(
            profile_payload=payload,
            open_session_key=open_session_key,
            current_condition=current_condition,
            risk_state=str(cycle_result.get("risk_state") or ""),
            quote_snapshot_id=int(exit_quote["quote_snapshot_id"]),
        )
        latest_trade_receipt: dict[str, Any] = {}
        decision_type = "review_only"
        policy_trace_id: int | None = None
        risk_verdict_id: int | None = None
        if exit_reason is not None:
            close_result = PaperTradeOperator(self.settings).close_cycle(
                session_key=open_session_key,
                quote_snapshot_id=int(exit_quote["quote_snapshot_id"]),
                close_reason=exit_reason,
                condition_run_id=str(cycle_result["condition_run_id"]),
            )
            decision_type = "paper_trade_closed"
            raw_policy_trace_id = close_result["policy_result"].get("trace_id")
            raw_risk_verdict_id = close_result["risk_result"].get("risk_verdict_id")
            policy_trace_id = (
                int(raw_policy_trace_id) if raw_policy_trace_id is not None else None
            )
            risk_verdict_id = (
                int(raw_risk_verdict_id) if raw_risk_verdict_id is not None else None
            )
            latest_trade_receipt = {
                "decision_type": decision_type,
                "session_key": open_session_key,
                "quote_snapshot_id": int(exit_quote["quote_snapshot_id"]),
                "condition_run_id": str(cycle_result["condition_run_id"]),
                "close_reason": exit_reason,
                "realized_pnl_usdc": close_result["settlement_result"]["realized_pnl_usdc"],
                "ending_cash_usdc": close_result["settlement_result"]["ending_cash_usdc"],
                "timestamp": utcnow().isoformat(),
            }
            self._write_trade_receipt(latest_trade_receipt)
            self._review_and_apply_closed_session(
                profile=profile,
                session_key=open_session_key,
                close_reason=exit_reason,
                exit_metrics=exit_metrics,
            )

        decision = self._record_decision(
            loop_run_id=loop_run_id,
            profile=profile,
            decision_type=decision_type,
            session_key=open_session_key,
            quote_snapshot_id=int(exit_quote["quote_snapshot_id"]),
            condition_run_id=str(cycle_result["condition_run_id"]),
            policy_trace_id=policy_trace_id,
            risk_verdict_id=risk_verdict_id,
            decision_payload={
                "cycle_id": cycle_result["cycle_id"],
                "exit_reason": exit_reason or "",
                "exit_metrics": exit_metrics,
                "latest_trade_receipt": latest_trade_receipt,
            },
            reason_codes=[f"exit_reason:{exit_reason}"] if exit_reason else ["exit_not_triggered"],
        )
        return {
            "latest_decision_id": decision["decision_id"],
            "latest_session_key": open_session_key,
            "cycle_id": cycle_result["cycle_id"],
            "latest_trade_receipt": latest_trade_receipt,
        }

    def _capture_close_quote(self, *, open_session_key: str) -> dict[str, object]:
        session = get_session(self.settings)
        try:
            paper_session = session.query(PaperSession).filter_by(session_key=open_session_key).one()
            position = (
                session.query(PaperPosition)
                .filter_by(session_id=paper_session.id)
                .order_by(PaperPosition.id.desc())
                .one()
            )
            decimals = self._resolve_token_decimals(session, position.mint)
        finally:
            session.close()

        amount = int(round(float(position.net_quantity) * (10**decimals)))
        usdc_mint = self._usdc_mint()
        return asyncio.run(
            CaptureRunner(self.settings).capture_jupiter_exact_quote(
                input_mint=position.mint,
                output_mint=usdc_mint,
                amount=amount,
                request_direction="token_to_usdc",
            )
        )

    def _evaluate_exit(
        self,
        *,
        profile_payload: dict[str, Any],
        open_session_key: str,
        current_condition: ConditionGlobalRegimeSnapshotV1 | None,
        risk_state: str,
        quote_snapshot_id: int,
    ) -> tuple[str | None, dict[str, Any]]:
        session = get_session(self.settings)
        try:
            paper_session = session.query(PaperSession).filter_by(session_key=open_session_key).one()
            position = (
                session.query(PaperPosition)
                .filter_by(session_id=paper_session.id)
                .order_by(PaperPosition.id.desc())
                .one()
            )
            quote = session.query(QuoteSnapshot).filter_by(id=quote_snapshot_id).one()
            decimals = self._resolve_token_decimals(session, position.mint)
        finally:
            session.close()

        proceeds_usdc = int(quote.output_amount) / (10**6)
        pnl_usdc = proceeds_usdc - float(position.cost_basis_usdc)
        pnl_bps = (
            (pnl_usdc / float(position.cost_basis_usdc)) * 10_000.0
            if position.cost_basis_usdc
            else 0.0
        )
        bars_held = max(
            0,
            int(
                (utcnow() - ensure_utc(paper_session.opened_at)).total_seconds()
                // int(profile_payload["cadence_minutes"] * 60)
            ),
        )
        semantic_regime = getattr(current_condition, "semantic_regime", "") or ""

        if pnl_bps <= -float(profile_payload["stop_loss_bps"]):
            return "stop_loss", {
                "pnl_usdc": pnl_usdc,
                "pnl_bps": pnl_bps,
                "bars_held": bars_held,
                "semantic_regime": semantic_regime,
            }
        if pnl_bps >= float(profile_payload["take_profit_bps"]):
            return "take_profit", {
                "pnl_usdc": pnl_usdc,
                "pnl_bps": pnl_bps,
                "bars_held": bars_held,
                "semantic_regime": semantic_regime,
            }
        if bars_held >= int(profile_payload["time_stop_bars"]):
            return "time_stop", {
                "pnl_usdc": pnl_usdc,
                "pnl_bps": pnl_bps,
                "bars_held": bars_held,
                "semantic_regime": semantic_regime,
            }
        if semantic_regime in {"risk_off", "no_trade"}:
            return "regime_degraded", {
                "pnl_usdc": pnl_usdc,
                "pnl_bps": pnl_bps,
                "bars_held": bars_held,
                "semantic_regime": semantic_regime,
            }
        if risk_state != "allowed":
            return "risk_disallowed", {
                "pnl_usdc": pnl_usdc,
                "pnl_bps": pnl_bps,
                "bars_held": bars_held,
                "semantic_regime": semantic_regime,
            }
        return None, {
            "pnl_usdc": pnl_usdc,
            "pnl_bps": pnl_bps,
            "bars_held": bars_held,
            "semantic_regime": semantic_regime,
        }

    def _review_and_apply_closed_session(
        self,
        *,
        profile: dict[str, Any],
        session_key: str,
        close_reason: str,
        exit_metrics: dict[str, Any],
    ) -> None:
        patch, summary = self._build_profile_patch(
            profile_payload=profile["payload"],
            close_reason=close_reason,
            exit_metrics=exit_metrics,
        )
        if not patch:
            return

        artifact_dir = self.settings.data_dir / "paper_runtime" / "cycles" / session_key
        adjustment_payload = {
            "story_id": "PAPER-001",
            "stage": "paper_practice",
            "paper_session_key": session_key,
            "close_reason": close_reason,
            "patch_keys": sorted(patch.keys()),
            "profile_patch": patch,
            "active_profile_id": profile["profile_id"],
            "active_revision_id": profile["active_revision_id"],
            "exit_metrics": exit_metrics,
            "summary": summary,
            "governance_scope": "paper_practice",
        }
        write_json_artifact(
            artifact_dir / "paper_profile_adjustment_summary.json",
            adjustment_payload,
            owner_type="paper_session",
            owner_key=session_key,
            artifact_type="paper_profile_adjustment_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "paper_profile_adjustment_report.qmd",
            render_qmd(
                "proposal.qmd",
                title="paper profile adjustment summary",
                summary_lines=[
                    f"- session key: `{session_key}`",
                    f"- close reason: `{close_reason}`",
                    f"- patch keys: `{', '.join(sorted(patch.keys()))}`",
                ],
                sections=[
                    ("Summary", [summary]),
                    (
                        "Patch",
                        [f"- `{key}`: `{value}`" for key, value in sorted(patch.items())],
                    ),
                    (
                        "Exit Metrics",
                        [f"- `{key}`: `{value}`" for key, value in sorted(exit_metrics.items())],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="paper_session",
            owner_key=session_key,
            artifact_type="paper_profile_adjustment_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        proposal = create_improvement_proposal(
            artifact_dir=artifact_dir,
            proposal_kind="paper_profile_adjustment_follow_on",
            source_owner_type="paper_session",
            source_owner_key=session_key,
            governance_scope="paper_practice",
            title="Review one bounded paper-only profile adjustment before the next autonomous paper cycle",
            summary=summary,
            hypothesis=(
                "Applying a bounded paper-only profile adjustment should improve the next "
                "paper session without mutating YAML policy, risk code, or live authority."
            ),
            next_test=(
                "Run proposal review and comparison on the bounded paper profile patch, then "
                "apply it only if the accepted patch stays inside the allowed paper-only keys."
            ),
            metrics={
                "realized_pnl_usdc": float(exit_metrics.get("pnl_usdc") or 0.0),
                "realized_pnl_bps": float(exit_metrics.get("pnl_bps") or 0.0),
                "bars_held": float(exit_metrics.get("bars_held") or 0.0),
                "patch_size": float(len(patch)),
            },
            reason_codes=[
                "paper_only_profile_mutation",
                f"close_reason:{close_reason}",
                "proposal_only_follow_on",
            ],
            settings=self.settings,
        )
        review_result = ProposalReviewer(self.settings).review_proposal(proposal["proposal_id"])
        comparison_result = ProposalComparator(self.settings).compare_proposals(
            proposal_ids=[proposal["proposal_id"]],
            proposal_kind="paper_profile_adjustment_follow_on",
            choose_top=True,
        )
        if (
            review_result["decision"] == "reviewed_accept"
            and comparison_result["selected_proposal_id"] == proposal["proposal_id"]
        ):
            self._apply_profile_patch(
                profile_id=profile["profile_id"],
                patch=patch,
                summary=summary,
                source_proposal_id=proposal["proposal_id"],
                source_review_id=review_result["review_id"],
                source_comparison_id=comparison_result["comparison_id"],
            )

    def _apply_profile_patch(
        self,
        *,
        profile_id: str,
        patch: dict[str, Any],
        summary: str,
        source_proposal_id: str,
        source_review_id: str,
        source_comparison_id: str,
    ) -> dict[str, Any]:
        session = get_session(self.settings)
        try:
            profile_row = session.query(PaperPracticeProfileV1).filter_by(profile_id=profile_id).one()
            active_revision = (
                session.query(PaperPracticeProfileRevisionV1)
                .filter_by(revision_id=profile_row.active_revision_id)
                .one()
            )
            payload = orjson.loads(active_revision.applied_parameter_json)
            payload.update(patch)
            active_revision.status = "superseded"
            created_at = utcnow()
            revision_index = (
                session.query(PaperPracticeProfileRevisionV1)
                .filter_by(profile_id=profile_id)
                .count()
                + 1
            )
            new_revision_id = f"paper_profile_revision_{uuid.uuid4().hex[:12]}"
            session.add(
                PaperPracticeProfileRevisionV1(
                    revision_id=new_revision_id,
                    profile_id=profile_id,
                    revision_index=revision_index,
                    status="active",
                    mutation_source="proposal_accept",
                    source_proposal_id=source_proposal_id,
                    source_review_id=source_review_id,
                    source_comparison_id=source_comparison_id,
                    applied_parameter_json=orjson.dumps(payload).decode(),
                    allowed_mutation_keys_json=orjson.dumps(list(_ALLOWED_PROFILE_KEYS)).decode(),
                    summary=summary,
                    created_at=created_at,
                )
            )
            profile_row.active_revision_id = new_revision_id
            profile_row.updated_at = created_at
            session.commit()
            serialized = {
                "profile_id": profile_id,
                "active_revision_id": new_revision_id,
                "payload": payload,
            }
        finally:
            session.close()

        self._write_profile_receipt(serialized, mutation_source="proposal_accept")
        self._write_profile_revision_artifacts(
            profile_id=profile_id,
            revision_id=new_revision_id,
            payload=payload,
            summary=summary,
            mutation_source="proposal_accept",
        )
        return serialized

    def _record_decision(
        self,
        *,
        loop_run_id: str,
        profile: dict[str, Any],
        decision_type: str,
        session_key: str,
        quote_snapshot_id: int | None,
        condition_run_id: str | None,
        policy_trace_id: int | None,
        risk_verdict_id: int | None,
        decision_payload: dict[str, Any],
        reason_codes: list[str],
    ) -> dict[str, Any]:
        created_at = utcnow()
        decision_id = f"paper_practice_decision_{uuid.uuid4().hex[:12]}"
        session = get_session(self.settings)
        try:
            session.add(
                PaperPracticeDecisionV1(
                    decision_id=decision_id,
                    loop_run_id=loop_run_id,
                    profile_id=profile["profile_id"],
                    profile_revision_id=profile["active_revision_id"],
                    decision_type=decision_type,
                    session_key=session_key or None,
                    quote_snapshot_id=quote_snapshot_id,
                    condition_run_id=condition_run_id,
                    policy_trace_id=policy_trace_id,
                    risk_verdict_id=risk_verdict_id,
                    decision_payload_json=orjson.dumps(decision_payload).decode(),
                    reason_codes_json=orjson.dumps(reason_codes).decode(),
                    created_at=created_at,
                )
            )
            session.commit()
        finally:
            session.close()
        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "paper_practice"
            / "decisions"
            / loop_run_id
            / decision_id
        )
        write_json_artifact(
            artifact_dir / "decision.json",
            {
                "decision_id": decision_id,
                "decision_type": decision_type,
                "loop_run_id": loop_run_id,
                "profile_id": profile["profile_id"],
                "profile_revision_id": profile["active_revision_id"],
                "session_key": session_key or "",
                "quote_snapshot_id": quote_snapshot_id,
                "condition_run_id": condition_run_id or "",
                "policy_trace_id": policy_trace_id,
                "risk_verdict_id": risk_verdict_id,
                "decision_payload": decision_payload,
                "reason_codes": reason_codes,
                "created_at": created_at.isoformat(),
            },
            owner_type="paper_practice_decision",
            owner_key=decision_id,
            artifact_type="paper_practice_decision",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "proposal_review.qmd",
                title=f"paper practice decision: {decision_type}",
                summary_lines=[
                    f"- decision id: `{decision_id}`",
                    f"- loop run id: `{loop_run_id}`",
                    f"- profile id: `{profile['profile_id']}`",
                    f"- decision type: `{decision_type}`",
                    f"- session key: `{session_key or 'none'}`",
                ],
                sections=[
                    ("Reason Codes", [f"- `{code}`" for code in reason_codes] or ["- none"]),
                    (
                        "Decision Payload",
                        [f"- `{key}`: `{value}`" for key, value in sorted(decision_payload.items())],
                    ),
                ],
                generated_at=created_at,
            ),
            owner_type="paper_practice_decision",
            owner_key=decision_id,
            artifact_type="paper_practice_decision_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        return {
            "decision_id": decision_id,
            "decision_type": decision_type,
            "created_at": created_at.isoformat(),
        }

    def _update_loop_run(
        self,
        *,
        loop_run_id: str,
        status: str,
        iterations_completed: int,
        latest_decision_id: str | None,
        latest_session_key: str | None,
        last_cycle_id: str | None,
        finished_at=None,
    ) -> None:
        session = get_session(self.settings)
        try:
            row = session.query(PaperPracticeLoopRunV1).filter_by(loop_run_id=loop_run_id).one()
            row.status = status
            row.iterations_completed = iterations_completed
            if latest_decision_id is not None:
                row.latest_decision_id = latest_decision_id
            if latest_session_key is not None:
                row.latest_session_key = latest_session_key
            if last_cycle_id is not None:
                row.last_cycle_id = last_cycle_id
            if finished_at is not None:
                row.finished_at = finished_at
            session.commit()
        finally:
            session.close()

    def _select_open_session(self, session) -> PaperSession | None:
        return (
            session.query(PaperSession)
            .filter_by(status="open")
            .order_by(desc(PaperSession.opened_at), desc(PaperSession.id))
            .first()
        )

    def _cooldown_active(self, cooldown_bars: int, cadence_minutes: int) -> bool:
        session = get_session(self.settings)
        try:
            latest_closed = (
                session.query(PaperSession)
                .filter_by(status="closed")
                .order_by(desc(PaperSession.closed_at), desc(PaperSession.id))
                .first()
            )
        finally:
            session.close()
        if latest_closed is None or latest_closed.closed_at is None:
            return False
        elapsed_bars = int(
            max(
                0,
                (utcnow() - ensure_utc(latest_closed.closed_at)).total_seconds()
                // max(60, cadence_minutes * 60),
            )
        )
        return elapsed_bars < cooldown_bars

    def _load_profile_strategy_selection(
        self,
        profile_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return PaperTradeOperator(self.settings)._load_advisory_strategy_selection(
            strategy_report_path=Path(profile_payload["strategy_report_path"]),
            preferred_family=(profile_payload.get("preferred_family") or None),
        )

    def _historical_entry_blocked(
        self,
        *,
        profile_payload: dict[str, Any],
        strategy_selection: dict[str, Any],
        semantic_regime: str,
        confidence: float,
    ) -> bool:
        if semantic_regime not in set(profile_payload["regime_allowlist"]):
            return True
        if confidence < float(profile_payload["minimum_condition_confidence"]):
            return True
        target_label = str(strategy_selection.get("target_label") or "")
        if target_label != "up":
            return True
        allowed_regimes = {
            str(item) for item in (strategy_selection.get("allowed_regimes") or [])
        }
        return semantic_regime not in allowed_regimes

    def _historical_exit_reason(
        self,
        *,
        profile_payload: dict[str, Any],
        semantic_regime: str,
        pnl_usdc: float,
        pnl_bps: float,
        bars_held: int,
    ) -> str | None:
        if pnl_bps <= -float(profile_payload["stop_loss_bps"]):
            return "stop_loss"
        if pnl_bps >= float(profile_payload["take_profit_bps"]):
            return "take_profit"
        if bars_held >= int(profile_payload["time_stop_bars"]):
            return "time_stop"
        if semantic_regime in {"risk_off", "no_trade"}:
            return "regime_degraded"
        return None

    def _load_backtest_price_history(self) -> pd.DataFrame:
        session = get_session(self.settings)
        try:
            rows = (
                session.query(MarketCandle)
                .filter_by(venue="massive", product_id="X:SOLUSD")
                .order_by(MarketCandle.start_time_utc.asc(), MarketCandle.id.asc())
                .all()
            )
        finally:
            session.close()
        if not rows:
            raise RuntimeError(
                "Missing Massive SOL replay candles for historical walk-forward. "
                "Run `d5 capture massive-minute-aggs --full-free-tier` first."
            )
        frame = pd.DataFrame(
            [
                {
                    "start_time_utc": ensure_utc(row.start_time_utc),
                    "close": float(row.close),
                }
                for row in rows
                if row.close is not None
            ]
        )
        if frame.empty:
            raise RuntimeError("Massive SOL replay candles are empty after normalization.")
        frame["start_time_utc"] = pd.to_datetime(frame["start_time_utc"], utc=True)
        return frame.sort_values("start_time_utc").reset_index(drop=True)

    def _lookup_backtest_price(
        self,
        price_history: pd.DataFrame,
        bucket_time: pd.Timestamp,
    ) -> float:
        candidates = price_history.loc[price_history["start_time_utc"] <= bucket_time]
        if candidates.empty:
            candidates = price_history.loc[price_history["start_time_utc"] >= bucket_time]
        if candidates.empty:
            raise RuntimeError(f"Missing replay price near bucket {bucket_time.isoformat()}")
        price = float(candidates.iloc[-1]["close"])
        if price <= 0:
            raise RuntimeError(f"Replay price must be positive at bucket {bucket_time.isoformat()}")
        return price

    def _review_and_apply_backtest_window(
        self,
        *,
        profile: dict[str, Any],
        session_key: str,
        close_reason: str,
        exit_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        patch, summary = self._build_profile_patch(
            profile_payload=profile["payload"],
            close_reason=close_reason,
            exit_metrics=exit_metrics,
        )
        if not patch:
            return {"proposal_id": "", "applied": False}

        artifact_dir = self.settings.data_dir / "research" / "paper_practice" / "replay_windows" / session_key
        adjustment_payload = {
            "story_id": "PAPER-001",
            "stage": "paper_practice_backtest",
            "backtest_session_key": session_key,
            "close_reason": close_reason,
            "patch_keys": sorted(patch.keys()),
            "profile_patch": patch,
            "active_profile_id": profile["profile_id"],
            "active_revision_id": profile["active_revision_id"],
            "exit_metrics": exit_metrics,
            "summary": summary,
            "governance_scope": "paper_practice",
        }
        write_json_artifact(
            artifact_dir / "paper_profile_adjustment_summary.json",
            adjustment_payload,
            owner_type="backtest_session",
            owner_key=session_key,
            artifact_type="paper_profile_adjustment_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "paper_profile_adjustment_report.qmd",
            render_qmd(
                "proposal.qmd",
                title="backtest paper profile adjustment summary",
                summary_lines=[
                    f"- backtest session key: `{session_key}`",
                    f"- close reason: `{close_reason}`",
                    f"- patch keys: `{', '.join(sorted(patch.keys()))}`",
                ],
                sections=[
                    ("Summary", [summary]),
                    (
                        "Patch",
                        [f"- `{key}`: `{value}`" for key, value in sorted(patch.items())],
                    ),
                    (
                        "Exit Metrics",
                        [f"- `{key}`: `{value}`" for key, value in sorted(exit_metrics.items())],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="backtest_session",
            owner_key=session_key,
            artifact_type="paper_profile_adjustment_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )
        proposal = create_improvement_proposal(
            artifact_dir=artifact_dir,
            proposal_kind="paper_profile_adjustment_follow_on",
            source_owner_type="backtest_session",
            source_owner_key=session_key,
            governance_scope="paper_practice",
            title="Review one bounded paper-only profile adjustment after the historical replay window",
            summary=summary,
            hypothesis=(
                "Applying a bounded paper-only profile adjustment should improve the next "
                "walk-forward window without widening live authority."
            ),
            next_test=(
                "Review the bounded paper profile patch, then replay the next historical "
                "window with the selected profile revision."
            ),
            metrics={
                "realized_pnl_usdc": float(exit_metrics.get("pnl_usdc") or 0.0),
                "realized_pnl_bps": float(exit_metrics.get("pnl_bps") or 0.0),
                "bars_held": float(exit_metrics.get("bars_held") or 0.0),
                "patch_size": float(len(patch)),
            },
            reason_codes=[
                "paper_only_profile_mutation",
                f"close_reason:{close_reason}",
                "proposal_only_follow_on",
                "historical_replay_window",
            ],
            settings=self.settings,
        )
        review_result = ProposalReviewer(self.settings).review_proposal(proposal["proposal_id"])
        comparison_result = ProposalComparator(self.settings).compare_proposals(
            proposal_ids=[proposal["proposal_id"]],
            proposal_kind="paper_profile_adjustment_follow_on",
            choose_top=True,
        )
        applied = False
        if (
            review_result["decision"] == "reviewed_accept"
            and comparison_result["selected_proposal_id"] == proposal["proposal_id"]
        ):
            self._apply_profile_patch(
                profile_id=profile["profile_id"],
                patch=patch,
                summary=summary,
                source_proposal_id=proposal["proposal_id"],
                source_review_id=review_result["review_id"],
                source_comparison_id=comparison_result["comparison_id"],
            )
            applied = True
        return {"proposal_id": proposal["proposal_id"], "applied": applied}

    def _write_status_receipts(
        self,
        *,
        profile: dict[str, Any],
        latest_trade_receipt: dict[str, Any],
        loop_state: dict[str, Any],
    ) -> None:
        status_payload = {
            "profile_id": profile["profile_id"],
            "active_revision_id": profile["active_revision_id"],
            "profile_payload": profile["payload"],
            "loop_state": loop_state,
            "updated_at": utcnow().isoformat(),
        }
        write_json_artifact(
            self.settings.repo_root / ".ai" / "dropbox" / "state" / "paper_practice_status.json",
            status_payload,
            owner_type="paper_practice",
            owner_key=profile["profile_id"],
            artifact_type="paper_practice_status_receipt",
            settings=self.settings,
        )
        if latest_trade_receipt:
            self._write_trade_receipt(latest_trade_receipt)
        self._write_profile_receipt(profile, mutation_source="status_refresh")

    def _write_trade_receipt(self, payload: dict[str, Any]) -> None:
        write_json_artifact(
            self.settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "paper_practice_latest_trade_receipt.json",
            payload,
            owner_type="paper_practice",
            owner_key=str(payload.get("session_key") or "no_session"),
            artifact_type="paper_practice_latest_trade_receipt",
            settings=self.settings,
        )

    def _write_profile_receipt(
        self,
        profile: dict[str, Any],
        *,
        mutation_source: str,
    ) -> None:
        payload = {
            "profile_id": profile["profile_id"],
            "active_revision_id": profile["active_revision_id"],
            "profile_payload": profile["payload"],
            "mutation_source": mutation_source,
            "updated_at": utcnow().isoformat(),
        }
        write_json_artifact(
            self.settings.repo_root
            / ".ai"
            / "dropbox"
            / "state"
            / "paper_practice_latest_profile_revision.json",
            payload,
            owner_type="paper_practice",
            owner_key=profile["profile_id"],
            artifact_type="paper_practice_latest_profile_revision",
            settings=self.settings,
        )

    def _write_profile_revision_artifacts(
        self,
        *,
        profile_id: str,
        revision_id: str,
        payload: dict[str, Any],
        summary: str,
        mutation_source: str,
    ) -> None:
        artifact_dir = (
            self.settings.data_dir
            / "research"
            / "paper_practice"
            / "profiles"
            / profile_id
            / revision_id
        )
        serialized = {
            "profile_id": profile_id,
            "revision_id": revision_id,
            "mutation_source": mutation_source,
            "summary": summary,
            "payload": payload,
            "updated_at": utcnow().isoformat(),
        }
        write_json_artifact(
            artifact_dir / "profile_revision.json",
            serialized,
            owner_type="paper_practice_profile",
            owner_key=revision_id,
            artifact_type="paper_practice_profile_revision",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            render_qmd(
                "proposal.qmd",
                title=f"paper practice profile revision: {revision_id}",
                summary_lines=[
                    f"- profile id: `{profile_id}`",
                    f"- revision id: `{revision_id}`",
                    f"- mutation source: `{mutation_source}`",
                ],
                sections=[
                    ("Summary", [summary]),
                    (
                        "Payload",
                        [f"- `{key}`: `{value}`" for key, value in sorted(payload.items())],
                    ),
                ],
                generated_at=utcnow(),
            ),
            owner_type="paper_practice_profile",
            owner_key=revision_id,
            artifact_type="paper_practice_profile_revision_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

    def _resolve_token_decimals(self, session, mint: str) -> int:
        registry_row = session.query(TokenRegistry).filter_by(mint=mint).first()
        if registry_row is not None and registry_row.decimals is not None:
            return int(registry_row.decimals)
        metadata_row = (
            session.query(TokenMetadataSnapshot)
            .filter_by(mint=mint)
            .order_by(desc(TokenMetadataSnapshot.captured_at), desc(TokenMetadataSnapshot.id))
            .first()
        )
        if metadata_row is not None and metadata_row.decimals is not None:
            return int(metadata_row.decimals)
        raise RuntimeError(f"Missing decimals for tracked mint: {mint}")

    def _build_profile_patch(
        self,
        *,
        profile_payload: dict[str, Any],
        close_reason: str,
        exit_metrics: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        current_confidence = float(profile_payload["minimum_condition_confidence"])
        current_cooldown = int(profile_payload["cooldown_bars"])
        current_time_stop = int(profile_payload["time_stop_bars"])
        patch: dict[str, Any] = {}
        if close_reason in {"stop_loss", "risk_disallowed", "regime_degraded"}:
            patch["minimum_condition_confidence"] = round(min(0.95, current_confidence + 0.05), 2)
            patch["cooldown_bars"] = min(12, current_cooldown + 1)
            summary = (
                "The paper session closed under adverse conditions, so the next paper-only "
                "profile should wait for slightly higher confidence and a longer cooldown."
            )
            return patch, summary
        if close_reason == "time_stop":
            patch["time_stop_bars"] = max(4, current_time_stop - 2)
            patch["minimum_condition_confidence"] = round(min(0.9, current_confidence + 0.02), 2)
            summary = (
                "The paper session timed out, so the next paper-only profile should shorten "
                "the hold window and ask for a slightly stronger entry signal."
            )
            return patch, summary
        if close_reason == "take_profit" and float(exit_metrics.get("pnl_usdc") or 0.0) > 0:
            patch["minimum_condition_confidence"] = round(max(0.55, current_confidence - 0.02), 2)
            summary = (
                "The paper session hit take profit cleanly, so the next paper-only profile "
                "can allow a slightly less strict confidence threshold."
            )
            return patch, summary
        return {}, ""

    def _default_profile_payload(self) -> dict[str, Any]:
        return {
            "instrument_pair": "SOL/USDC",
            "context_anchors": ["BTC/USD", "ETH/USD"],
            "cadence_minutes": 15,
            "max_open_sessions": 1,
            "long_only": True,
            "regime_allowlist": ["long_friendly"],
            "minimum_condition_confidence": 0.60,
            "stop_loss_bps": 100,
            "take_profit_bps": 150,
            "time_stop_bars": 16,
            "cooldown_bars": 4,
            "strategy_report_path": str(self.settings.repo_root / _DEFAULT_STRATEGY_REPORT),
            "preferred_family": "",
        }

    def _usdc_mint(self) -> str:
        return self._mint_for_symbol("USDC")

    def _mint_for_symbol(self, symbol: str) -> str:
        return next(
            mint
            for mint, hinted_symbol in self.settings.token_symbol_hints.items()
            if hinted_symbol == symbol
        )
