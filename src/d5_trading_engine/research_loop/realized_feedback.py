"""Research-owned realized-feedback comparison over settlement truth."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import orjson
import pandas as pd

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.research_loop.shadow_runner import _SHADOW_RUN_NAME, ShadowRunner
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ExperimentMetric,
    ExperimentRealizedFeedbackV1,
    ExperimentRun,
    PaperFill,
    PaperPosition,
    PaperSessionReport,
)

log = get_logger(__name__)

_MATCH_METHOD = "feature_run+bucket_15m+mint+merge_asof_backward"
_MATCH_TOLERANCE = timedelta(minutes=5)
_ROLLUP_METRICS = (
    "realized_feedback_candidate_fills",
    "realized_feedback_matches",
    "realized_feedback_skipped",
    "realized_feedback_missing_reports",
    "realized_feedback_no_shadow_row",
)
_SHADOW_CONTEXT_COLUMNS = (
    "coinbase_product_id",
    "symbol",
    "matched_mint",
    "matched_bucket_5m_utc",
    "matched_bucket_15m_utc",
    "close",
    "atr_14",
    "condition_regime",
    "condition_confidence",
    "blocked_flag",
    "macro_context_available",
)


class RealizedFeedbackComparator:
    """Compare replayed shadow context against settlement-owned paper outcomes."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def compare_intraday_meta_stack_v1(self, *, experiment_run_id: str) -> dict[str, object]:
        experiment_run = self._load_experiment_run(experiment_run_id)
        config_payload = self._decode_config(experiment_run.config_json)
        dataset = ShadowRunner(self.settings)._rebuild_dataset_from_config(config_payload)
        label_columns = self._label_columns_from_config(
            config_payload=config_payload,
            dataset=dataset,
        )
        source_feature_run_id = config_payload["regime_feature_run_id"]
        candidate_fills = self._load_candidate_fills(source_feature_run_id=source_feature_run_id)
        comparison_rows, rollup_counts = self._build_comparison_rows(
            experiment_run_id=experiment_run_id,
            source_feature_run_id=source_feature_run_id,
            dataset=dataset,
            candidate_fills=candidate_fills,
            label_columns=label_columns,
        )
        self._persist_feedback(
            experiment_run_id=experiment_run_id,
            comparison_rows=comparison_rows,
            rollup_counts=rollup_counts,
        )

        summary = {
            "experiment_run_id": experiment_run_id,
            **rollup_counts,
            "rows_written": len(comparison_rows),
        }
        log.info("realized_feedback_compared", **summary)
        return summary

    def _load_experiment_run(self, experiment_run_id: str) -> ExperimentRun:
        session = get_session(self.settings)
        try:
            run = session.query(ExperimentRun).filter_by(run_id=experiment_run_id).first()
            if run is None:
                raise RuntimeError(
                    f"Missing experiment_run for realized feedback: {experiment_run_id}"
                )
            if run.experiment_name != _SHADOW_RUN_NAME:
                raise RuntimeError(
                    f"Unsupported experiment_name for realized feedback: {run.experiment_name}"
                )
            return run
        finally:
            session.close()

    def _decode_config(self, config_json: str | None) -> dict[str, object]:
        if not config_json:
            raise RuntimeError("Experiment run has no config_json for realized feedback replay.")

        payload = orjson.loads(config_json)
        if not isinstance(payload, dict):
            raise RuntimeError("Experiment config_json must decode to an object payload.")
        if not isinstance(payload.get("regime_feature_run_id"), str):
            raise RuntimeError("Experiment config_json is missing regime_feature_run_id.")
        return payload

    def _label_columns_from_config(
        self,
        *,
        config_payload: dict[str, object],
        dataset: pd.DataFrame,
    ) -> list[str]:
        raw_specs = config_payload.get("label_specs")
        if not isinstance(raw_specs, dict):
            return []
        return [name for name in raw_specs if isinstance(name, str) and name in dataset.columns]

    def _load_candidate_fills(self, *, source_feature_run_id: str) -> list[dict[str, Any]]:
        session = get_session(self.settings)
        try:
            fills = (
                session.query(PaperFill)
                .filter_by(source_feature_run_id=source_feature_run_id)
                .order_by(PaperFill.created_at.asc(), PaperFill.id.asc())
                .all()
            )
            if not fills:
                return []

            session_ids = sorted({fill.session_id for fill in fills})
            snapshot_ids = sorted({fill.condition_snapshot_id for fill in fills})
            snapshots = {
                row.id: row
                for row in session.query(ConditionGlobalRegimeSnapshotV1)
                .filter(ConditionGlobalRegimeSnapshotV1.id.in_(snapshot_ids))
                .all()
            }
            positions = {
                (row.session_id, row.mint): row
                for row in session.query(PaperPosition)
                .filter(PaperPosition.session_id.in_(session_ids))
                .all()
            }
            reports: dict[int, PaperSessionReport] = {}
            report_rows = (
                session.query(PaperSessionReport)
                .filter(PaperSessionReport.session_id.in_(session_ids))
                .order_by(
                    PaperSessionReport.session_id.asc(),
                    PaperSessionReport.created_at.desc(),
                    PaperSessionReport.id.desc(),
                )
                .all()
            )
            for report in report_rows:
                reports.setdefault(report.session_id, report)

            return [
                {
                    "paper_fill": fill,
                    "condition_snapshot": snapshots.get(fill.condition_snapshot_id),
                    "paper_position": positions.get((fill.session_id, fill.output_mint)),
                    "paper_session_report": reports.get(fill.session_id),
                }
                for fill in fills
            ]
        finally:
            session.close()

    def _build_comparison_rows(
        self,
        *,
        experiment_run_id: str,
        source_feature_run_id: str,
        dataset: pd.DataFrame,
        candidate_fills: list[dict[str, Any]],
        label_columns: list[str],
    ) -> tuple[list[dict[str, object]], dict[str, int]]:
        rows: list[dict[str, object]] = []
        metrics = {
            "realized_feedback_candidate_fills": len(candidate_fills),
            "realized_feedback_matches": 0,
            "realized_feedback_skipped": 0,
            "realized_feedback_missing_reports": 0,
            "realized_feedback_no_shadow_row": 0,
        }
        if not candidate_fills:
            return rows, metrics

        valid_fill_rows: list[dict[str, object]] = []
        for fill_context in candidate_fills:
            fill = fill_context["paper_fill"]
            snapshot = fill_context["condition_snapshot"]
            fill_created_at = ensure_utc(fill.created_at)
            bucket_15m_utc = ensure_utc(snapshot.bucket_start_utc) if snapshot is not None else None
            reason_codes: list[str] = []
            if snapshot is None:
                reason_codes.append("condition_snapshot_missing")
            if fill_created_at is None:
                reason_codes.append("paper_fill_created_at_missing")

            if reason_codes:
                rows.append(
                    self._build_feedback_row(
                        experiment_run_id=experiment_run_id,
                        source_feature_run_id=source_feature_run_id,
                        fill_context=fill_context,
                        comparison_state="skipped",
                        match_bucket_15m_utc=bucket_15m_utc,
                        match_bucket_5m_utc=None,
                        shadow_context={},
                        reason_codes=reason_codes,
                    )
                )
                metrics["realized_feedback_skipped"] += 1
                continue

            valid_fill_rows.append(
                {
                    "paper_fill_id": fill.id,
                    "paper_session_id": fill.session_id,
                    "paper_position_id": (
                        fill_context["paper_position"].id
                        if fill_context["paper_position"] is not None
                        else None
                    ),
                    "paper_session_report_id": (
                        fill_context["paper_session_report"].id
                        if fill_context["paper_session_report"] is not None
                        else None
                    ),
                    "matched_mint": fill.output_mint,
                    "matched_bucket_15m_utc": pd.Timestamp(bucket_15m_utc),
                    "fill_created_at": pd.Timestamp(fill_created_at),
                    "fill_context": fill_context,
                }
            )

        merged = self._match_shadow_rows(
            dataset=dataset,
            valid_fill_rows=valid_fill_rows,
            label_columns=label_columns,
        )
        for item in merged:
            fill_context = item["fill_context"]
            shadow_context = item["shadow_context"]
            reason_codes = list(item["reason_codes"])
            if fill_context["paper_session_report"] is None:
                reason_codes.append("paper_session_report_missing")
                metrics["realized_feedback_missing_reports"] += 1
            if fill_context["paper_position"] is None:
                reason_codes.append("paper_position_missing")

            comparison_state = "matched" if shadow_context else "skipped"
            if comparison_state == "matched":
                metrics["realized_feedback_matches"] += 1
            else:
                metrics["realized_feedback_skipped"] += 1
                if "no_shadow_row_within_tolerance" in reason_codes:
                    metrics["realized_feedback_no_shadow_row"] += 1

            rows.append(
                self._build_feedback_row(
                    experiment_run_id=experiment_run_id,
                    source_feature_run_id=source_feature_run_id,
                    fill_context=fill_context,
                    comparison_state=comparison_state,
                    match_bucket_15m_utc=item["matched_bucket_15m_utc"],
                    match_bucket_5m_utc=item["matched_bucket_5m_utc"],
                    shadow_context=shadow_context,
                    reason_codes=reason_codes,
                )
            )

        return rows, metrics

    def _match_shadow_rows(
        self,
        *,
        dataset: pd.DataFrame,
        valid_fill_rows: list[dict[str, object]],
        label_columns: list[str],
    ) -> list[dict[str, object]]:
        if not valid_fill_rows:
            return []

        if dataset.empty:
            return [
                {
                    "fill_context": item["fill_context"],
                    "matched_bucket_15m_utc": self._ensure_pydatetime(
                        item["matched_bucket_15m_utc"]
                    ),
                    "matched_bucket_5m_utc": None,
                    "shadow_context": {},
                    "reason_codes": ["no_shadow_row_within_tolerance"],
                }
                for item in valid_fill_rows
            ]

        left = pd.DataFrame(valid_fill_rows)
        right = dataset.copy()
        right = right.rename(
            columns={
                "bucket_5m": "matched_bucket_5m_utc",
                "bucket_15m": "matched_bucket_15m_utc",
                "mint": "matched_mint",
            }
        )
        right["matched_bucket_5m_utc"] = pd.to_datetime(right["matched_bucket_5m_utc"], utc=True)
        right["matched_bucket_15m_utc"] = pd.to_datetime(right["matched_bucket_15m_utc"], utc=True)

        join_columns = [
            "matched_mint",
            "matched_bucket_15m_utc",
            "matched_bucket_5m_utc",
            *[column for column in _SHADOW_CONTEXT_COLUMNS if column in right.columns],
            *label_columns,
        ]
        join_columns = list(dict.fromkeys(join_columns))
        right = (
            right[join_columns]
            .sort_values(["matched_bucket_15m_utc", "matched_mint", "matched_bucket_5m_utc"])
            .reset_index(drop=True)
        )
        left = left.sort_values(
            ["matched_bucket_15m_utc", "matched_mint", "fill_created_at"]
        ).reset_index(drop=True)

        merged = pd.merge_asof(
            left,
            right,
            left_on="fill_created_at",
            right_on="matched_bucket_5m_utc",
            by=["matched_bucket_15m_utc", "matched_mint"],
            direction="backward",
            tolerance=pd.Timedelta(_MATCH_TOLERANCE),
        )

        results: list[dict[str, object]] = []
        for merged_row in merged.to_dict(orient="records"):
            matched_bucket_5m = merged_row.get("matched_bucket_5m_utc")
            shadow_context = self._build_shadow_context(
                merged_row=merged_row,
                label_columns=label_columns,
            )
            reason_codes = [] if shadow_context else ["no_shadow_row_within_tolerance"]
            results.append(
                {
                    "fill_context": merged_row["fill_context"],
                    "matched_bucket_15m_utc": self._ensure_pydatetime(
                        merged_row["matched_bucket_15m_utc"]
                    ),
                    "matched_bucket_5m_utc": self._ensure_pydatetime(matched_bucket_5m),
                    "shadow_context": shadow_context,
                    "reason_codes": reason_codes,
                }
            )
        return results

    def _build_feedback_row(
        self,
        *,
        experiment_run_id: str,
        source_feature_run_id: str,
        fill_context: dict[str, Any],
        comparison_state: str,
        match_bucket_15m_utc,
        match_bucket_5m_utc,
        shadow_context: dict[str, object],
        reason_codes: list[str],
    ) -> dict[str, object]:
        fill = fill_context["paper_fill"]
        position = fill_context["paper_position"]
        report = fill_context["paper_session_report"]
        return {
            "experiment_run_id": experiment_run_id,
            "paper_fill_id": fill.id,
            "paper_session_id": fill.session_id,
            "paper_position_id": position.id if position is not None else None,
            "paper_session_report_id": report.id if report is not None else None,
            "source_feature_run_id": source_feature_run_id,
            "matched_mint": fill.output_mint,
            "matched_bucket_15m_utc": match_bucket_15m_utc,
            "matched_bucket_5m_utc": match_bucket_5m_utc,
            "comparison_state": comparison_state,
            "match_method": _MATCH_METHOD,
            "match_tolerance_seconds": int(_MATCH_TOLERANCE.total_seconds()),
            "shadow_context_json": self._encode_json(shadow_context),
            "realized_outcome_json": self._encode_json(
                {
                    "fill_price_usdc": fill.fill_price_usdc,
                    "input_amount": fill.input_amount,
                    "output_amount": fill.output_amount,
                    "fill_side": fill.fill_side,
                    "fill_role": fill.fill_role,
                    "position_net_quantity": (
                        position.net_quantity if position is not None else None
                    ),
                    "position_cost_basis_usdc": (
                        position.cost_basis_usdc if position is not None else None
                    ),
                    "report_cash_usdc": report.cash_usdc if report is not None else None,
                    "report_position_value_usdc": (
                        report.position_value_usdc if report is not None else None
                    ),
                    "report_equity_usdc": report.equity_usdc if report is not None else None,
                    "report_realized_pnl_usdc": (
                        report.realized_pnl_usdc if report is not None else None
                    ),
                    "report_unrealized_pnl_usdc": (
                        report.unrealized_pnl_usdc if report is not None else None
                    ),
                    "mark_method": report.mark_method if report is not None else None,
                }
            ),
            "reason_codes_json": self._encode_json(reason_codes),
            "created_at": utcnow(),
        }

    def _build_shadow_context(
        self,
        *,
        merged_row: dict[str, Any],
        label_columns: list[str],
    ) -> dict[str, object]:
        if pd.isna(merged_row.get("matched_bucket_5m_utc")):
            return {}

        payload: dict[str, object] = {}
        for column in (*_SHADOW_CONTEXT_COLUMNS, *label_columns):
            if column in merged_row:
                payload[column] = self._json_value(merged_row[column])
        return payload

    def _persist_feedback(
        self,
        *,
        experiment_run_id: str,
        comparison_rows: list[dict[str, object]],
        rollup_counts: dict[str, int],
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            (
                session.query(ExperimentRealizedFeedbackV1)
                .filter_by(experiment_run_id=experiment_run_id)
                .delete(synchronize_session=False)
            )
            (
                session.query(ExperimentMetric)
                .filter_by(experiment_run_id=experiment_run_id)
                .filter(ExperimentMetric.metric_name.in_(_ROLLUP_METRICS))
                .delete(synchronize_session=False)
            )

            session.add_all(
                ExperimentRealizedFeedbackV1(**row)
                for row in comparison_rows
            )
            session.add_all(
                ExperimentMetric(
                    experiment_run_id=experiment_run_id,
                    metric_name=metric_name,
                    metric_value=float(metric_value),
                    metric_metadata=None,
                    recorded_at=now,
                )
                for metric_name, metric_value in rollup_counts.items()
            )
            session.commit()
        finally:
            session.close()

    def _encode_json(self, payload: object) -> str:
        return orjson.dumps(payload).decode()

    def _json_value(self, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
        if hasattr(value, "isoformat") and callable(value.isoformat):
            return value.isoformat()
        if pd.isna(value):
            return None
        if hasattr(value, "item") and callable(value.item):
            return value.item()
        return value

    def _ensure_pydatetime(self, value):
        if value is None or pd.isna(value):
            return None
        if isinstance(value, pd.Timestamp):
            value = value.to_pydatetime()
        return ensure_utc(value)
