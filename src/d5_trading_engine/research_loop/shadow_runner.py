"""Shadow-mode evaluation for the intraday meta-stack."""

from __future__ import annotations

import math
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.condition.scorer import (
    _REFIT_CADENCE_BUCKETS,
    _TRAINING_WINDOW,
    ConditionScorer,
    RegimeHistoryResult,
)
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.features.materializer import _FEATURE_SET_NAME
from d5_trading_engine.models.ensemble_baselines import (
    RUNTIME_ADJACENT_MODELS,
    build_isolation_forest,
    build_random_forest_classifier,
    build_xgboost_classifier,
)
from d5_trading_engine.models.shadow_only import SHADOW_ONLY_MODELS
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.proposals import create_improvement_proposal
from d5_trading_engine.reporting.qmd import render_qmd
from d5_trading_engine.research_loop.registries import (
    CANONICAL_DIRECTION_LABEL_SPECS,
    load_instrument_scope,
    load_metrics_registry,
    load_strategy_registry,
)
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ExperimentMetric,
    ExperimentRun,
    FeatureMaterializationRun,
    FeatureSpotChainMacroMinuteV1,
    MarketCandle,
)

log = get_logger(__name__)

_SHADOW_RUN_NAME = "intraday_meta_stack_v1"
_LABEL_PROGRAM_RUN_NAME = "label_program_v1"
_STRATEGY_EVAL_RUN_NAME = "strategy_eval_v1"
_LABEL_SPECS = {
    "tb_60m_atr1x": 12,
    "tb_240m_atr1x": 48,
}
_ATR_WINDOW = 14
_TRAIN_RATIO = 0.8
_MIN_DATASET_ROWS = 64
_MONTE_CARLO_PATHS = 10_000
_CHRONOS_MODEL_ID = "amazon/chronos-2"
_ANCHOR_PRODUCT_PREFERENCE = ("SOL-USD", "BTC-USD", "ETH-USD")
_SPOT_MODEL_COLUMNS = [
    "jupiter_price_usd",
    "quote_count",
    "mean_quote_price_impact_pct",
    "mean_quote_response_latency_ms",
    "coinbase_close",
    "coinbase_trade_count",
    "coinbase_trade_size_sum",
    "coinbase_book_spread_bps",
    "chain_transfer_count",
    "chain_amount_in",
    "chain_amount_out",
    "fred_dff",
    "fred_t10y2y",
    "fred_vixcls",
    "fred_dgs10",
    "fred_dtwexbgs",
]
_REGIME_NUMERIC_COLUMNS = [
    "market_return_mean_15m",
    "market_return_std_15m",
    "market_realized_vol_15m",
    "market_volume_sum_15m",
    "market_trade_count_15m",
    "market_trade_size_sum_15m",
    "market_book_spread_bps_mean_15m",
    "market_return_mean_4h",
    "market_realized_vol_4h",
]
_DIRECTION_LABELS = ("up", "down", "flat", "invalid", "low_confidence")


class ShadowRunner:
    """Run bounded shadow evaluations from canonical truth and condition history."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def repo_root(self) -> Path:
        return self.settings.repo_root

    def run_label_program_v1(self) -> dict[str, object]:
        """Run the bounded canonical label-program loop."""
        inputs = self._prepare_shadow_inputs(label_specs=_LABEL_SPECS)
        dataset = self._attach_canonical_direction_labels(inputs["dataset"])
        metrics_registry = load_metrics_registry(self.repo_root)
        instrument_scope = load_instrument_scope(self.repo_root)

        run_id = f"experiment_{_LABEL_PROGRAM_RUN_NAME}_{uuid.uuid4().hex[:12]}"
        artifact_dir = self.settings.data_dir / "research" / "label_program_runs" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        config_payload = {
            "label_program": _LABEL_PROGRAM_RUN_NAME,
            "spot_feature_run_id": inputs["spot_feature_run_id"],
            "regime_feature_run_id": inputs["regime_feature_run_id"],
            "artifact_dir": str(artifact_dir),
            "label_specs": _LABEL_SPECS,
            "canonical_label_specs": CANONICAL_DIRECTION_LABEL_SPECS,
            "metrics_registry": metrics_registry.get("label_program", {}),
            "instrument_scope": instrument_scope.get("research_stage", {}),
        }

        self._start_experiment_run(
            run_id,
            experiment_name=_LABEL_PROGRAM_RUN_NAME,
            hypothesis=(
                "Canonical direction labels with explicit low-confidence and invalid windows "
                "should create a stronger foundation for strategy-family comparison."
            ),
            config_payload=config_payload,
        )

        try:
            candidate_report = self._build_label_program_candidate(
                run_id=run_id,
                dataset=dataset,
                metrics_registry=metrics_registry.get("label_program", {}),
            )
            self._record_label_program_metrics(run_id, candidate_report)
            self._write_label_program_artifacts(
                run_id=run_id,
                artifact_dir=artifact_dir,
                config_payload=config_payload,
                candidate_report=candidate_report,
                dataset=dataset,
            )
            dropbox_path = self._write_dropbox_research_artifact(
                "LABEL-001__label_program_candidate.json",
                candidate_report,
                owner_key=run_id,
            )
            proposal = create_improvement_proposal(
                artifact_dir=artifact_dir,
                proposal_kind="label_program_follow_on",
                source_owner_type="experiment_run",
                source_owner_key=run_id,
                governance_scope="research_loop",
                title="Review label-program evidence before widening strategy research",
                summary=(
                    "The canonical label program completed and emitted bounded evidence "
                    "artifacts. Follow-on work should stay proposal-only until the "
                    "operator reviews the strongest label family."
                ),
                hypothesis=(
                    "Improving label coverage and class balance for the strongest label "
                    "family should produce a cleaner input surface for governed challenger "
                    "evaluation."
                ),
                next_test=(
                    "Review the best-performing label family and run governed strategy "
                    "evaluation without changing runtime strategy or risk policy."
                ),
                metrics={
                    "family_count": len(candidate_report["families"]),
                    "eligible_family_count": sum(
                        1
                        for metrics in candidate_report["families"].values()
                        if metrics.get("eligible")
                    ),
                    "dropbox_artifact_written": 1.0 if dropbox_path.exists() else 0.0,
                },
                reason_codes=[
                    "operator_review_required",
                    "proposal_only_follow_on",
                    "no_runtime_promotion",
                ],
                settings=self.settings,
            )
            conclusion = (
                f"Label program complete. families={','.join(sorted(candidate_report['families']))} "
                f"eligible={candidate_report['auto_promotion_eligible']}"
            )
            self._finish_experiment_run(run_id, status="success", conclusion=conclusion)
        except Exception as exc:
            self._finish_experiment_run(run_id, status="failed", conclusion=str(exc))
            raise

        return {
            "run_id": run_id,
            "artifact_dir": str(artifact_dir),
            "families": sorted(candidate_report["families"]),
            "auto_promotion_eligible": candidate_report["auto_promotion_eligible"],
            "proposal_id": proposal["proposal_id"],
            "proposal_status": proposal["status"],
        }

    def run_strategy_eval_v1(self) -> dict[str, object]:
        """Run the bounded named strategy-family challenger loop."""
        inputs = self._prepare_shadow_inputs(label_specs=_LABEL_SPECS)
        dataset = self._attach_canonical_direction_labels(inputs["dataset"])
        metrics_registry = load_metrics_registry(self.repo_root)
        strategy_registry = load_strategy_registry(self.repo_root)

        run_id = f"experiment_{_STRATEGY_EVAL_RUN_NAME}_{uuid.uuid4().hex[:12]}"
        artifact_dir = self.settings.data_dir / "research" / "strategy_eval_runs" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        config_payload = {
            "strategy_eval": _STRATEGY_EVAL_RUN_NAME,
            "spot_feature_run_id": inputs["spot_feature_run_id"],
            "regime_feature_run_id": inputs["regime_feature_run_id"],
            "artifact_dir": str(artifact_dir),
            "label_specs": _LABEL_SPECS,
            "canonical_label_specs": CANONICAL_DIRECTION_LABEL_SPECS,
            "metrics_registry": metrics_registry.get("strategy_eval", {}),
            "strategy_registry_path": str(self.repo_root / ".ai" / "swarm" / "strategy_registry.yaml"),
        }

        self._start_experiment_run(
            run_id,
            experiment_name=_STRATEGY_EVAL_RUN_NAME,
            hypothesis=(
                "Named strategy families with explicit regime filters and anomaly vetoes "
                "should be comparable without widening runtime authority."
            ),
            config_payload=config_payload,
        )

        try:
            challenger_report = self._build_strategy_challenger_report(
                run_id=run_id,
                dataset=dataset,
                strategy_registry=strategy_registry,
                metrics_registry=metrics_registry.get("strategy_eval", {}),
            )
            self._record_strategy_eval_metrics(run_id, challenger_report)
            self._write_strategy_eval_artifacts(
                run_id=run_id,
                artifact_dir=artifact_dir,
                config_payload=config_payload,
                challenger_report=challenger_report,
                dataset=dataset,
            )
            dropbox_path = self.repo_root / ".ai" / "dropbox" / "research" / "STRAT-001__strategy_challenger_report.json"
            challenger_report["artifact_path"] = str(dropbox_path)
            dropbox_path = self._write_dropbox_research_artifact(
                "STRAT-001__strategy_challenger_report.json",
                challenger_report,
                owner_key=run_id,
            )
            proposal = create_improvement_proposal(
                artifact_dir=artifact_dir,
                proposal_kind="strategy_eval_follow_on",
                source_owner_type="experiment_run",
                source_owner_key=run_id,
                governance_scope="research_loop",
                title="Review challenger evidence before authorizing paper follow-on work",
                summary=(
                    "The governed challenger loop identified a current top family, but the "
                    "result remains advisory-only until the operator reviews the evidence."
                ),
                hypothesis=(
                    "Testing the top family under a tighter regime slice or more "
                    "conservative anomaly veto should improve expectancy stability without "
                    "changing runtime authority."
                ),
                next_test=(
                    "Review the top family and approve one bounded paper or backtest follow-on "
                    "experiment."
                ),
                metrics={
                    "family_count": len(challenger_report["families"]),
                    "eligible_family_count": sum(
                        1
                        for metrics in challenger_report["families"].values()
                        if metrics.get("eligible")
                    ),
                    "top_family_present": 1.0 if challenger_report.get("top_family") else 0.0,
                },
                reason_codes=[
                    "operator_review_required",
                    "proposal_only_follow_on",
                    "no_runtime_promotion",
                ],
                settings=self.settings,
            )
            conclusion = (
                f"Strategy evaluation complete. families={','.join(sorted(challenger_report['families']))} "
                f"eligible={challenger_report['auto_promotion_eligible']}"
            )
            self._finish_experiment_run(run_id, status="success", conclusion=conclusion)
        except Exception as exc:
            self._finish_experiment_run(run_id, status="failed", conclusion=str(exc))
            raise

        return {
            "run_id": run_id,
            "artifact_dir": str(artifact_dir),
            "families": sorted(challenger_report["families"]),
            "auto_promotion_eligible": challenger_report["auto_promotion_eligible"],
            "top_family": challenger_report["top_family"],
            "proposal_id": proposal["proposal_id"],
            "proposal_status": proposal["status"],
        }

    def _prepare_shadow_inputs(
        self,
        *,
        label_specs: dict[str, int],
    ) -> dict[str, object]:
        regime_result = ConditionScorer(self.settings).build_walk_forward_regime_history()
        spot_feature_run = self._latest_feature_run(_FEATURE_SET_NAME)
        spot_frame = self._load_spot_feature_frame(spot_feature_run.run_id)
        if spot_frame.empty:
            raise RuntimeError("No spot-chain feature rows available for shadow evaluation.")

        market_bars_5m = self._load_market_bars(
            sorted(spot_frame["coinbase_product_id"].dropna().unique()),
            bucket_minutes=5,
        )
        if market_bars_5m.empty:
            raise RuntimeError("No 5-minute market bars available for shadow evaluation.")

        label_frame = self._attach_triple_barrier_labels(
            market_bars_5m,
            label_specs=label_specs,
        )
        dataset = self._build_meta_dataset(spot_frame, regime_result.history, label_frame)
        if len(dataset) < _MIN_DATASET_ROWS:
            raise RuntimeError(
                f"Need at least {_MIN_DATASET_ROWS} joined rows for shadow evaluation; "
                f"found {len(dataset)}."
            )
        return {
            "dataset": dataset,
            "spot_feature_run_id": spot_feature_run.run_id,
            "regime_feature_run_id": regime_result.feature_run_id,
            "regime_result": regime_result,
            "market_bars_5m": market_bars_5m,
        }

    def run_intraday_meta_stack_v1(self) -> dict[str, object]:
        """Run the shadow meta-stack and persist experiment receipts."""
        inputs = self._prepare_shadow_inputs(label_specs=_LABEL_SPECS)
        regime_result = inputs["regime_result"]
        dataset = inputs["dataset"]
        market_bars_5m = inputs["market_bars_5m"]

        run_id = f"experiment_{_SHADOW_RUN_NAME}_{uuid.uuid4().hex[:12]}"
        artifact_dir = self._artifact_dir(run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        config_payload = {
            "shadow_run": _SHADOW_RUN_NAME,
            "spot_feature_run_id": inputs["spot_feature_run_id"],
            "regime_feature_run_id": regime_result.feature_run_id,
            "regime_model_family": regime_result.model_family,
            "macro_context_state": regime_result.macro_context_state,
            "regime_history_mode": "walk_forward",
            "regime_refit_cadence_buckets": _REFIT_CADENCE_BUCKETS,
            "regime_training_window_days": _TRAINING_WINDOW.days,
            "artifact_dir": str(artifact_dir),
            "label_specs": _LABEL_SPECS,
            "atr_window": _ATR_WINDOW,
            "train_ratio": _TRAIN_RATIO,
            "monte_carlo_paths": _MONTE_CARLO_PATHS,
            "runtime_adjacent_models": sorted(RUNTIME_ADJACENT_MODELS),
            "shadow_only_models": sorted(SHADOW_ONLY_MODELS),
        }
        self._start_experiment_run(
            run_id,
            experiment_name=_SHADOW_RUN_NAME,
            hypothesis=(
                "HMM-aligned regimes plus anomaly veto should improve the "
                "expected value of short-horizon crypto setups."
            ),
            config_payload=config_payload,
        )

        try:
            chronos_summary = self._run_chronos_and_monte_carlo(dataset, market_bars_5m)
            model_metrics = self._run_meta_models(dataset)
            if not model_metrics["families"]:
                raise RuntimeError("Shadow models did not produce any evaluable label families.")

            self._write_shadow_artifacts(
                run_id=run_id,
                artifact_dir=artifact_dir,
                config_payload=config_payload,
                chronos_summary=chronos_summary,
                model_metrics=model_metrics,
                dataset=dataset,
            )
            self._record_experiment_metrics(run_id, chronos_summary, model_metrics, dataset)
            from d5_trading_engine.research_loop.realized_feedback import (
                RealizedFeedbackComparator,
            )

            RealizedFeedbackComparator(self.settings).compare_intraday_meta_stack_v1(
                experiment_run_id=run_id
            )

            conclusion = (
                f"Shadow run complete. "
                f"chronos={chronos_summary['status']} "
                f"families={','.join(sorted(model_metrics['families']))}"
            )
            self._finish_experiment_run(run_id, status="success", conclusion=conclusion)
        except Exception as exc:
            self._finish_experiment_run(run_id, status="failed", conclusion=str(exc))
            raise

        return {
            "run_id": run_id,
            "artifact_dir": str(artifact_dir),
            "chronos_status": chronos_summary["status"],
            "families": sorted(model_metrics["families"]),
        }

    def _latest_feature_run(self, feature_set: str) -> FeatureMaterializationRun:
        session = get_session(self.settings)
        try:
            run = (
                session.query(FeatureMaterializationRun)
                .filter_by(feature_set=feature_set, status="success")
                .order_by(FeatureMaterializationRun.finished_at.desc())
                .first()
            )
            if run is None:
                raise RuntimeError(
                    f"No successful feature run exists for {feature_set}. "
                    f"Run `d5 materialize-features` first."
                )
            return run
        finally:
            session.close()

    def _load_spot_feature_frame(self, feature_run_id: str) -> pd.DataFrame:
        session = get_session(self.settings)
        try:
            rows = (
                session.query(FeatureSpotChainMacroMinuteV1)
                .filter_by(feature_run_id=feature_run_id)
                .order_by(FeatureSpotChainMacroMinuteV1.feature_minute_utc.asc())
                .all()
            )
        finally:
            session.close()

        frame = pd.DataFrame(
            [
                {
                    "feature_minute_utc": ensure_utc(row.feature_minute_utc),
                    "mint": row.mint,
                    "symbol": row.symbol,
                    "coinbase_product_id": row.coinbase_product_id,
                    **{column: getattr(row, column) for column in _SPOT_MODEL_COLUMNS},
                }
                for row in rows
                if row.coinbase_product_id
            ]
        )
        if frame.empty:
            return frame

        frame["feature_minute_utc"] = pd.to_datetime(frame["feature_minute_utc"], utc=True)
        frame["bucket_5m"] = frame["feature_minute_utc"].dt.floor("5min")
        frame["bucket_15m"] = frame["feature_minute_utc"].dt.floor("15min")
        frame = (
            frame.sort_values(["mint", "feature_minute_utc"])
            .groupby(["mint", "coinbase_product_id", "bucket_5m"], as_index=False)
            .tail(1)
            .reset_index(drop=True)
        )
        return frame

    def _load_market_bars(
        self,
        product_ids: list[str],
        *,
        bucket_minutes: int,
        atr_window: int = _ATR_WINDOW,
    ) -> pd.DataFrame:
        if not product_ids:
            return pd.DataFrame()

        session = get_session(self.settings)
        try:
            candle_rows = (
                session.query(MarketCandle)
                .filter(MarketCandle.product_id.in_(product_ids))
                .order_by(MarketCandle.product_id.asc(), MarketCandle.start_time_utc.asc())
                .all()
            )
        finally:
            session.close()

        frame = pd.DataFrame(
            [
                {
                    "product_id": row.product_id,
                    "start_time_utc": ensure_utc(row.start_time_utc),
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                }
                for row in candle_rows
                if row.granularity in {"ONE_MINUTE", "60", "60s"}
            ]
        )
        if frame.empty:
            return frame

        bucket_label = f"bucket_{bucket_minutes}m"
        frame["start_time_utc"] = pd.to_datetime(frame["start_time_utc"], utc=True)
        frame[bucket_label] = frame["start_time_utc"].dt.floor(f"{bucket_minutes}min")
        grouped = (
            frame.sort_values(["product_id", "start_time_utc"])
            .groupby(["product_id", bucket_label], as_index=False)
            .agg(
                open=("open", "first"),
                high=("high", "max"),
                low=("low", "min"),
                close=("close", "last"),
                volume=("volume", "sum"),
            )
        )
        grouped["prev_close"] = grouped.groupby("product_id")["close"].shift(1)
        grouped["true_range"] = grouped.apply(
            lambda row: max(
                float(row["high"] - row["low"]),
                abs(float(row["high"] - row["prev_close"])) if pd.notna(row["prev_close"]) else 0.0,
                abs(float(row["low"] - row["prev_close"])) if pd.notna(row["prev_close"]) else 0.0,
            ),
            axis=1,
        )
        grouped["atr_14"] = grouped.groupby("product_id")["true_range"].transform(
            lambda series: series.rolling(atr_window, min_periods=min(5, atr_window)).mean()
        )
        grouped.rename(columns={bucket_label: "bucket_start_utc"}, inplace=True)
        return grouped

    def _attach_triple_barrier_labels(
        self,
        bars: pd.DataFrame,
        *,
        label_specs: dict[str, int] | None = None,
    ) -> pd.DataFrame:
        resolved_label_specs = label_specs or _LABEL_SPECS
        labeled = bars.copy()
        for label_name, horizon_bars in resolved_label_specs.items():
            labeled[label_name] = np.nan
            for _product_id, group in labeled.groupby("product_id", sort=False):
                product_group = group.reset_index()
                label_values: list[float] = []
                for idx, row in product_group.iterrows():
                    atr = float(row["atr_14"]) if pd.notna(row["atr_14"]) else 0.0
                    if atr <= 0.0:
                        label_values.append(np.nan)
                        continue

                    upper_barrier = float(row["close"]) + atr
                    lower_barrier = float(row["close"]) - atr
                    future = product_group.iloc[idx + 1 : idx + 1 + horizon_bars]
                    if future.empty:
                        label_values.append(np.nan)
                        continue

                    upper_hits = future.index[future["high"] >= upper_barrier].tolist()
                    lower_hits = future.index[future["low"] <= lower_barrier].tolist()
                    if upper_hits and (not lower_hits or upper_hits[0] < lower_hits[0]):
                        label_values.append(1.0)
                    else:
                        label_values.append(0.0)

                labeled.loc[group.index, label_name] = label_values

        return labeled

    def _rebuild_dataset_from_config(self, config_payload: dict[str, object]) -> pd.DataFrame:
        spot_feature_run_id = self._config_string(config_payload, "spot_feature_run_id")
        regime_feature_run_id = self._config_string(config_payload, "regime_feature_run_id")
        label_specs = self._resolve_label_specs(config_payload)
        atr_window = self._resolve_positive_int(
            config_payload.get("atr_window"),
            default=_ATR_WINDOW,
        )

        spot_frame = self._load_spot_feature_frame(spot_feature_run_id)
        if spot_frame.empty:
            raise RuntimeError(
                "No spot-chain feature rows exist for replayed "
                f"spot_feature_run_id={spot_feature_run_id}."
            )

        market_bars_5m = self._load_market_bars(
            sorted(spot_frame["coinbase_product_id"].dropna().unique()),
            bucket_minutes=5,
            atr_window=atr_window,
        )
        if market_bars_5m.empty:
            raise RuntimeError(
                "No 5-minute market bars available while replaying shadow experiment inputs."
            )

        label_frame = self._attach_triple_barrier_labels(
            market_bars_5m,
            label_specs=label_specs,
        )
        regime_result = self._rebuild_walk_forward_regime_history(regime_feature_run_id)
        return self._build_meta_dataset(spot_frame, regime_result.history, label_frame)

    def _rebuild_walk_forward_regime_history(self, feature_run_id: str) -> RegimeHistoryResult:
        condition_scorer = ConditionScorer(self.settings)
        feature_run = self._feature_run_by_id(feature_run_id)
        history = condition_scorer._load_feature_history(feature_run.run_id)
        if history.empty:
            raise RuntimeError(
                f"No global regime feature rows exist for replayed feature_run_id={feature_run_id}."
            )

        macro_context_state = condition_scorer._macro_context_state(feature_run)
        scored_history, state_semantics, model_family = (
            condition_scorer._build_walk_forward_history_frame(
                history,
                macro_context_state=macro_context_state,
            )
        )
        if scored_history.empty:
            raise RuntimeError(
                "Replay for feature_run_id="
                f"{feature_run_id} produced no walk-forward regime history."
            )

        latest_row = scored_history.iloc[-1]
        return RegimeHistoryResult(
            feature_run_id=feature_run.run_id,
            history=scored_history,
            state_semantics=state_semantics,
            model_family=model_family,
            macro_context_state=macro_context_state,
            training_window_start_utc=latest_row["training_window_start_utc"].to_pydatetime(),
            training_window_end_utc=latest_row["training_window_end_utc"].to_pydatetime(),
        )

    def _feature_run_by_id(self, run_id: str) -> FeatureMaterializationRun:
        session = get_session(self.settings)
        try:
            run = session.query(FeatureMaterializationRun).filter_by(run_id=run_id).first()
            if run is None:
                raise RuntimeError(f"Missing feature materialization run: {run_id}")
            return run
        finally:
            session.close()

    def _config_string(self, config_payload: dict[str, object], key: str) -> str:
        value = config_payload.get(key)
        if not isinstance(value, str) or not value:
            raise RuntimeError(f"Shadow replay config is missing a valid {key}.")
        return value

    def _resolve_label_specs(self, config_payload: dict[str, object]) -> dict[str, int]:
        raw_specs = config_payload.get("label_specs")
        if raw_specs is None:
            return dict(_LABEL_SPECS)
        if not isinstance(raw_specs, dict):
            raise RuntimeError("Shadow replay config has an invalid label_specs payload.")

        resolved: dict[str, int] = {}
        for label_name, horizon in raw_specs.items():
            if not isinstance(label_name, str):
                raise RuntimeError("Shadow replay config has a non-string label name.")
            resolved[label_name] = self._resolve_positive_int(horizon, default=1)
        return resolved

    def _resolve_positive_int(self, value: object, *, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            raise RuntimeError("Shadow replay config expected a positive integer, not a boolean.")
        resolved = int(value)
        if resolved <= 0:
            raise RuntimeError("Shadow replay config expected a positive integer value.")
        return resolved

    def _build_meta_dataset(
        self,
        spot_frame: pd.DataFrame,
        regime_history: pd.DataFrame,
        label_frame: pd.DataFrame,
    ) -> pd.DataFrame:
        regime_frame = regime_history.copy()
        regime_frame = regime_frame.rename(
            columns={
                "bucket_start_utc": "bucket_15m",
                "confidence": "condition_confidence",
                "semantic_regime": "condition_regime",
            }
        )
        regime_frame["blocked_flag"] = regime_frame["condition_regime"].isin(
            {"risk_off", "no_trade"}
        ).astype(int)

        dataset = spot_frame.merge(
            label_frame[
                [
                    "product_id",
                    "bucket_start_utc",
                    "close",
                    "atr_14",
                    *list(_LABEL_SPECS),
                ]
            ],
            how="inner",
            left_on=["coinbase_product_id", "bucket_5m"],
            right_on=["product_id", "bucket_start_utc"],
        )
        dataset = dataset.merge(
            regime_frame[
                [
                    "bucket_15m",
                    *_REGIME_NUMERIC_COLUMNS,
                    "macro_context_available",
                    "condition_regime",
                    "condition_confidence",
                    "blocked_flag",
                    "model_epoch_bucket_start_utc",
                    "training_window_start_utc",
                    "training_window_end_utc",
                ]
            ],
            how="inner",
            on="bucket_15m",
        )
        dataset = dataset.sort_values(
            ["bucket_5m", "coinbase_product_id", "mint"]
        ).reset_index(drop=True)
        return dataset

    def _attach_canonical_direction_labels(self, dataset: pd.DataFrame) -> pd.DataFrame:
        labeled = dataset.copy()
        labeled = labeled.sort_values(
            ["coinbase_product_id", "mint", "bucket_5m"]
        ).reset_index(drop=True)

        for family_name, spec in CANONICAL_DIRECTION_LABEL_SPECS.items():
            label_column = family_name
            return_column = f"{family_name}__future_return"
            threshold_column = f"{family_name}__threshold_return"
            labeled[label_column] = "invalid"
            labeled[return_column] = np.nan
            labeled[threshold_column] = np.nan

            for _, group in labeled.groupby(["coinbase_product_id", "mint"], sort=False):
                group_index = group.index.tolist()
                closes = group["close"].astype(float).to_numpy()
                atr_values = group["atr_14"].astype(float).to_numpy()
                confidence = group["condition_confidence"].astype(float).to_numpy()
                horizon_bars = int(spec["horizon_bars"])
                atr_multiple = float(spec["atr_multiple"])
                low_conf_threshold = float(spec["low_confidence_threshold"])
                labels: list[str] = []
                future_returns: list[float] = []
                threshold_returns: list[float] = []

                for idx, close_value in enumerate(closes):
                    if idx + horizon_bars >= len(closes):
                        labels.append("invalid")
                        future_returns.append(np.nan)
                        threshold_returns.append(np.nan)
                        continue

                    atr_value = float(atr_values[idx]) if not np.isnan(atr_values[idx]) else 0.0
                    if atr_value <= 0.0 or close_value <= 0.0:
                        labels.append("invalid")
                        future_returns.append(np.nan)
                        threshold_returns.append(np.nan)
                        continue

                    future_close = float(closes[idx + horizon_bars])
                    future_return = (future_close / close_value) - 1.0
                    threshold_return = (atr_multiple * atr_value) / close_value
                    future_returns.append(future_return)
                    threshold_returns.append(threshold_return)

                    if confidence[idx] < low_conf_threshold:
                        labels.append("low_confidence")
                    elif future_return >= threshold_return:
                        labels.append("up")
                    elif future_return <= (-1.0 * threshold_return):
                        labels.append("down")
                    else:
                        labels.append("flat")

                labeled.loc[group_index, label_column] = labels
                labeled.loc[group_index, return_column] = future_returns
                labeled.loc[group_index, threshold_column] = threshold_returns

        return labeled

    def _build_feature_matrix(self, dataset: pd.DataFrame) -> pd.DataFrame:
        feature_matrix = dataset[
            _SPOT_MODEL_COLUMNS
            + _REGIME_NUMERIC_COLUMNS
            + ["macro_context_available", "condition_confidence", "blocked_flag"]
        ].copy()
        feature_matrix = feature_matrix.ffill().bfill().fillna(0.0)
        regime_dummies = pd.get_dummies(dataset["condition_regime"], prefix="regime")
        feature_matrix = pd.concat([feature_matrix, regime_dummies], axis=1)
        return feature_matrix

    def _compute_class_entropy(self, labels: pd.Series) -> float:
        if labels.empty:
            return 0.0
        distribution = labels.value_counts(normalize=True)
        if distribution.empty or len(distribution) <= 1:
            return 0.0
        entropy = float(-(distribution * np.log2(distribution)).sum())
        max_entropy = math.log2(len(distribution))
        if max_entropy <= 0:
            return 0.0
        return entropy / max_entropy

    def _build_label_program_candidate(
        self,
        *,
        run_id: str,
        dataset: pd.DataFrame,
        metrics_registry: dict[str, Any],
    ) -> dict[str, Any]:
        thresholds = metrics_registry.get("thresholds") or {}
        min_rows = int(thresholds.get("min_rows", _MIN_DATASET_ROWS))
        min_valid_coverage = float(thresholds.get("min_valid_coverage", 0.55))
        max_invalid_rate = float(thresholds.get("max_invalid_rate", 0.35))
        max_low_confidence_rate = float(thresholds.get("max_low_confidence_rate", 0.55))

        families: dict[str, dict[str, Any]] = {}
        auto_promotion_eligible = True
        for family_name in CANONICAL_DIRECTION_LABEL_SPECS:
            family_frame = dataset[[family_name, "condition_regime", f"{family_name}__future_return"]].copy()
            rows_total = int(len(family_frame))
            class_counts = {
                label: int((family_frame[family_name] == label).sum())
                for label in _DIRECTION_LABELS
            }
            valid_mask = family_frame[family_name].isin({"up", "down", "flat"})
            valid_frame = family_frame.loc[valid_mask]
            valid_coverage = float(len(valid_frame) / rows_total) if rows_total else 0.0
            invalid_rate = float(class_counts["invalid"] / rows_total) if rows_total else 1.0
            low_confidence_rate = (
                float(class_counts["low_confidence"] / rows_total) if rows_total else 1.0
            )
            normalized_entropy = self._compute_class_entropy(valid_frame[family_name])
            regime_distribution = (
                valid_frame.groupby("condition_regime")[family_name]
                .value_counts()
                .unstack(fill_value=0)
                .to_dict(orient="index")
                if not valid_frame.empty
                else {}
            )
            return_by_label = {
                label: (
                    float(valid_frame.loc[valid_frame[family_name] == label, f"{family_name}__future_return"].mean())
                    if not valid_frame.loc[valid_frame[family_name] == label].empty
                    else None
                )
                for label in ("up", "down", "flat")
            }
            eligible = (
                rows_total >= min_rows
                and valid_coverage >= min_valid_coverage
                and invalid_rate <= max_invalid_rate
                and low_confidence_rate <= max_low_confidence_rate
            )
            auto_promotion_eligible = auto_promotion_eligible and eligible
            families[family_name] = {
                "rows_total": rows_total,
                "valid_rows": int(len(valid_frame)),
                "valid_coverage": valid_coverage,
                "invalid_rate": invalid_rate,
                "low_confidence_rate": low_confidence_rate,
                "normalized_class_entropy": normalized_entropy,
                "class_counts": class_counts,
                "regime_distribution": regime_distribution,
                "future_return_mean_by_label": return_by_label,
                "eligible": eligible,
            }

        return {
            "artifact_type": "label_program_candidate",
            "run_id": run_id,
            "story_id": "LABEL-001",
            "stage": "regime_and_label_truth",
            "families": families,
            "auto_promotion_eligible": auto_promotion_eligible,
            "next_story_id": "STRAT-001" if auto_promotion_eligible else None,
            "generated_at": utcnow().isoformat(),
        }

    def _build_strategy_challenger_report(
        self,
        *,
        run_id: str,
        dataset: pd.DataFrame,
        strategy_registry: dict[str, Any],
        metrics_registry: dict[str, Any],
    ) -> dict[str, Any]:
        thresholds = metrics_registry.get("thresholds") or {}
        min_rows_total = int(thresholds.get("min_rows_total", _MIN_DATASET_ROWS))
        min_rows_train = int(thresholds.get("min_rows_train", 16))
        min_rows_test = int(thresholds.get("min_rows_test", 8))
        min_xgb_accuracy = float(thresholds.get("min_xgb_accuracy", 0.52))
        min_xgb_auc = float(thresholds.get("min_xgb_auc", 0.52))
        min_expected_positive_return = float(thresholds.get("min_expected_positive_return", 0.0))

        feature_matrix = self._build_feature_matrix(dataset)
        split_index = max(int(len(dataset) * _TRAIN_RATIO), 1)
        isolation_forest = build_isolation_forest(contamination=0.08)
        isolation_forest.fit(feature_matrix.iloc[:split_index])
        anomaly_predictions = isolation_forest.predict(feature_matrix)
        scored = dataset.copy()
        scored["anomaly_flag"] = (anomaly_predictions == -1).astype(int)

        families: dict[str, dict[str, Any]] = {}
        top_family = None
        top_score = -1.0
        auto_promotion_eligible = False
        for family_name, config in (strategy_registry.get("families") or {}).items():
            label_family = str(config.get("label_family") or "")
            target_label = str(config.get("target_label") or "")
            allowed_regimes = set(config.get("allowed_regimes") or [])
            require_anomaly_veto = bool(config.get("require_anomaly_veto"))
            if label_family not in scored.columns:
                continue

            family_frame = scored.loc[
                scored[label_family].isin({"up", "down", "flat"})
                & scored["condition_regime"].isin(allowed_regimes)
            ].copy()
            if len(family_frame) < min_rows_total:
                continue

            family_matrix = feature_matrix.loc[family_frame.index]
            family_frame["target_positive"] = (family_frame[label_family] == target_label).astype(int)
            if family_frame["target_positive"].nunique() < 2:
                continue

            family_split = self._find_viable_walk_forward_split(
                family_frame,
                target_column="target_positive",
                min_train=min_rows_train,
                min_test=min_rows_test,
            )
            train_frame = family_frame.iloc[:family_split]
            test_frame = family_frame.iloc[family_split:]
            train_matrix = family_matrix.loc[train_frame.index]
            test_matrix = family_matrix.loc[test_frame.index]

            if require_anomaly_veto:
                test_mask = test_frame["anomaly_flag"] == 0
                test_frame = test_frame.loc[test_mask]
                test_matrix = test_matrix.loc[test_frame.index]

            if (
                len(train_matrix) < min_rows_train
                or len(test_matrix) < min_rows_test
                or train_frame["target_positive"].nunique() < 2
            ):
                train_frame = family_frame.iloc[:family_split]
                test_frame = family_frame.iloc[family_split:]
                train_matrix = family_matrix.loc[train_frame.index]
                test_matrix = family_matrix.loc[test_frame.index]
                if (
                    len(train_matrix) < min_rows_train
                    or len(test_matrix) < min_rows_test
                    or train_frame["target_positive"].nunique() < 2
                ):
                    continue

            y_train = train_frame["target_positive"].astype(int)
            y_test = test_frame["target_positive"].astype(int)

            rf = build_random_forest_classifier()
            rf.fit(train_matrix, y_train)
            rf_probs = rf.predict_proba(test_matrix)[:, 1]
            rf_preds = (rf_probs >= 0.5).astype(int)

            xgb = build_xgboost_classifier()
            xgb.fit(train_matrix, y_train)
            xgb_probs = xgb.predict_proba(test_matrix)[:, 1]
            xgb_preds = (xgb_probs >= 0.5).astype(int)

            future_return_column = f"{label_family}__future_return"
            positive_expectancy = (
                float(test_frame.loc[xgb_preds == 1, future_return_column].mean())
                if (xgb_preds == 1).any() and future_return_column in test_frame
                else 0.0
            )
            xgb_auc = self._safe_auc(y_test, xgb_probs)
            eligible = (
                float(accuracy_score(y_test, xgb_preds)) >= min_xgb_accuracy
                and (xgb_auc or 0.0) >= min_xgb_auc
                and (positive_expectancy or 0.0) >= min_expected_positive_return
            )
            family_payload = {
                "rows_total": int(len(family_frame)),
                "rows_train": int(len(train_matrix)),
                "rows_test": int(len(test_matrix)),
                "anomaly_filter_applied": 1 if require_anomaly_veto else 0,
                "rf_accuracy": float(accuracy_score(y_test, rf_preds)),
                "rf_auc": self._safe_auc(y_test, rf_probs),
                "xgb_accuracy": float(accuracy_score(y_test, xgb_preds)),
                "xgb_auc": xgb_auc,
                "positive_expectancy": positive_expectancy,
                "eligible": eligible,
                "label_family": label_family,
                "target_label": target_label,
                "allowed_regimes": sorted(allowed_regimes),
            }
            families[family_name] = family_payload
            score = float(family_payload["xgb_accuracy"]) + float(family_payload["xgb_auc"] or 0.0)
            if score > top_score:
                top_score = score
                top_family = family_name
            auto_promotion_eligible = auto_promotion_eligible or eligible

        return {
            "artifact_type": "strategy_challenger_report",
            "run_id": run_id,
            "story_id": "STRAT-001",
            "stage": "strategy_research",
            "families": families,
            "top_family": top_family,
            "auto_promotion_eligible": auto_promotion_eligible,
            "generated_at": utcnow().isoformat(),
        }

    def _run_meta_models(self, dataset: pd.DataFrame) -> dict[str, object]:
        feature_matrix = dataset[
            _SPOT_MODEL_COLUMNS
            + _REGIME_NUMERIC_COLUMNS
            + ["macro_context_available", "condition_confidence", "blocked_flag"]
        ].copy()
        feature_matrix = feature_matrix.ffill().bfill().fillna(0.0)
        regime_dummies = pd.get_dummies(dataset["condition_regime"], prefix="regime")
        feature_matrix = pd.concat([feature_matrix, regime_dummies], axis=1)

        split_index = max(int(len(dataset) * _TRAIN_RATIO), 1)
        isolation_forest = build_isolation_forest(contamination=0.08)
        isolation_forest.fit(feature_matrix.iloc[:split_index])
        anomaly_predictions = isolation_forest.predict(feature_matrix)
        dataset = dataset.copy()
        dataset["anomaly_flag"] = (anomaly_predictions == -1).astype(int)

        families: dict[str, dict[str, float | int | None]] = {}
        summary = {
            "families": families,
            "anomaly_rate": float(dataset["anomaly_flag"].mean()),
        }
        for label_name in _LABEL_SPECS:
            family_frame = dataset.loc[dataset[label_name].notna()].copy()
            if len(family_frame) < _MIN_DATASET_ROWS:
                continue

            family_matrix = feature_matrix.loc[family_frame.index]
            family_split = max(int(len(family_frame) * _TRAIN_RATIO), 1)
            train_frame = family_frame.iloc[:family_split]
            test_frame = family_frame.iloc[family_split:]
            train_mask = train_frame["anomaly_flag"] == 0
            test_mask = test_frame["anomaly_flag"] == 0
            train_matrix = family_matrix.loc[train_frame.index][train_mask]
            test_matrix = family_matrix.loc[test_frame.index][test_mask]
            y_train = train_frame.loc[train_mask, label_name].astype(int)
            y_test = test_frame.loc[test_mask, label_name].astype(int)
            anomaly_filter_applied = 1

            if (
                len(train_matrix) < 16
                or len(test_matrix) < 8
                or y_train.nunique() < 2
                or y_test.nunique() < 2
            ):
                train_matrix = family_matrix.loc[train_frame.index]
                test_matrix = family_matrix.loc[test_frame.index]
                y_train = train_frame[label_name].astype(int)
                y_test = test_frame[label_name].astype(int)
                anomaly_filter_applied = 0

            if (
                len(train_matrix) < 16
                or len(test_matrix) < 8
                or y_train.nunique() < 2
                or y_test.nunique() < 2
            ):
                continue

            rf = build_random_forest_classifier()
            rf.fit(train_matrix, y_train)
            rf_probs = rf.predict_proba(test_matrix)[:, 1]
            rf_preds = (rf_probs >= 0.5).astype(int)

            xgb = build_xgboost_classifier()
            xgb.fit(train_matrix, y_train)
            xgb_probs = xgb.predict_proba(test_matrix)[:, 1]
            xgb_preds = (xgb_probs >= 0.5).astype(int)

            families[label_name] = {
                "rows_total": int(len(family_frame)),
                "rows_train": int(len(train_matrix)),
                "rows_test": int(len(test_matrix)),
                "anomaly_filter_applied": anomaly_filter_applied,
                "positive_rate_train": float(y_train.mean()),
                "positive_rate_test": float(y_test.mean()),
                "rf_accuracy": float(accuracy_score(y_test, rf_preds)),
                "rf_auc": self._safe_auc(y_test, rf_probs),
                "xgb_accuracy": float(accuracy_score(y_test, xgb_preds)),
                "xgb_auc": self._safe_auc(y_test, xgb_probs),
            }

        return summary

    def _run_chronos_and_monte_carlo(
        self,
        dataset: pd.DataFrame,
        market_bars_5m: pd.DataFrame,
    ) -> dict[str, object]:
        anchor_product = self._select_anchor_product(dataset)
        market_bars_15m = self._load_market_bars([anchor_product], bucket_minutes=15)
        if market_bars_15m.empty or len(market_bars_15m) < 32:
            return {
                "status": "skipped:no_anchor_15m_history",
                "anchor_product_id": anchor_product,
            }

        anchor_series = market_bars_15m.loc[
            market_bars_15m["product_id"] == anchor_product,
            "close",
        ].tail(256)
        if len(anchor_series) < 32:
            return {
                "status": "skipped:insufficient_anchor_series",
                "anchor_product_id": anchor_product,
            }

        try:
            pipeline = self._load_chronos_pipeline()
            predictions = pipeline.predict(
                [anchor_series.to_numpy(dtype=float)],
                prediction_length=16,
                context_length=min(len(anchor_series), 256),
            )
            quantiles = list(getattr(pipeline, "quantiles", [0.1, 0.5, 0.9]))
            forecast = predictions[0].detach().cpu().numpy()
            if forecast.ndim == 3:
                forecast = forecast[0]

            lower = self._pick_quantile(forecast, quantiles, 0.1)
            median = self._pick_quantile(forecast, quantiles, 0.5)
            upper = self._pick_quantile(forecast, quantiles, 0.9)

            monte_carlo = {
                "horizon_8": self._monte_carlo_summary(
                    float(anchor_series.iloc[-1]),
                    median[:8],
                    lower[:8],
                    upper[:8],
                ),
                "horizon_16": self._monte_carlo_summary(
                    float(anchor_series.iloc[-1]),
                    median[:16],
                    lower[:16],
                    upper[:16],
                ),
            }
            fibonacci = self._fibonacci_confluence(
                market_bars_15m.loc[market_bars_15m["product_id"] == anchor_product, "close"],
                monte_carlo,
            )
            return {
                "status": "ok",
                "anchor_product_id": anchor_product,
                "quantiles": {
                    "0.1": lower.tolist(),
                    "0.5": median.tolist(),
                    "0.9": upper.tolist(),
                },
                "monte_carlo": monte_carlo,
                "fibonacci": fibonacci,
            }
        except Exception as exc:
            log.warning("chronos_shadow_skipped", reason=str(exc))
            return {
                "status": f"skipped:{type(exc).__name__}",
                "anchor_product_id": anchor_product,
                "error": str(exc),
            }

    def _load_chronos_pipeline(self):
        import torch
        from chronos import Chronos2Pipeline

        device_map = "cuda" if torch.cuda.is_available() else "cpu"
        return Chronos2Pipeline.from_pretrained(_CHRONOS_MODEL_ID, device_map=device_map)

    def _pick_quantile(self, forecast, quantiles: list[float], target: float):
        quantile_index = min(
            range(len(quantiles)),
            key=lambda idx: abs(float(quantiles[idx]) - target),
        )
        return forecast[quantile_index]

    def _monte_carlo_summary(
        self,
        start_price: float,
        median: np.ndarray,
        lower: np.ndarray,
        upper: np.ndarray,
    ) -> dict[str, float]:
        rng = np.random.default_rng(42)
        paths = np.full(_MONTE_CARLO_PATHS, start_price, dtype=float)
        z_score_90 = 1.2815515655446004
        previous_median = start_price
        horizon = len(median)
        for step in range(horizon):
            target_median = float(median[step])
            drift = (target_median / previous_median) - 1.0 if previous_median else 0.0
            spread = max(float(upper[step] - lower[step]), abs(target_median) * 0.001)
            sigma = max(spread / (2.0 * z_score_90 * max(previous_median, 1e-6)), 1e-4)
            sampled_returns = rng.normal(loc=drift, scale=sigma, size=_MONTE_CARLO_PATHS)
            paths = np.maximum(1e-6, paths * (1.0 + sampled_returns))
            previous_median = target_median

        return {
            "paths": float(_MONTE_CARLO_PATHS),
            "terminal_median": float(np.median(paths)),
            "probability_box_low": float(np.quantile(paths, 0.025)),
            "probability_box_high": float(np.quantile(paths, 0.975)),
        }

    def _fibonacci_confluence(
        self,
        close_series: pd.Series,
        monte_carlo: dict[str, dict[str, float]],
    ) -> dict[str, object]:
        recent = close_series.tail(48)
        if recent.empty:
            return {"levels": {}, "confluence": {}}
        swing_high = float(recent.max())
        swing_low = float(recent.min())
        if not math.isfinite(swing_high) or not math.isfinite(swing_low) or swing_high <= swing_low:
            return {"levels": {}, "confluence": {}}

        levels = {
            "0.382": swing_high - ((swing_high - swing_low) * 0.382),
            "0.500": swing_high - ((swing_high - swing_low) * 0.5),
            "0.618": swing_high - ((swing_high - swing_low) * 0.618),
            "0.786": swing_high - ((swing_high - swing_low) * 0.786),
        }
        confluence: dict[str, list[str]] = {}
        for horizon, summary in monte_carlo.items():
            hits = [
                level_name
                for level_name, level_value in levels.items()
                if summary["probability_box_low"] <= level_value <= summary["probability_box_high"]
            ]
            confluence[horizon] = hits
        return {"levels": levels, "confluence": confluence}

    def _select_anchor_product(self, dataset: pd.DataFrame) -> str:
        available = [product for product in dataset["coinbase_product_id"].dropna().unique()]
        for preferred in _ANCHOR_PRODUCT_PREFERENCE:
            if preferred in available:
                return preferred
        return str(available[0])

    def _safe_auc(self, y_true, probabilities) -> float | None:
        if len(set(y_true)) < 2:
            return None
        return float(roc_auc_score(y_true, probabilities))

    def _find_viable_walk_forward_split(
        self,
        frame: pd.DataFrame,
        *,
        target_column: str,
        min_train: int,
        min_test: int,
    ) -> int:
        total_rows = len(frame)
        preferred = max(int(total_rows * _TRAIN_RATIO), min_train)
        max_split = total_rows - min_test
        if max_split <= min_train:
            return max(min(preferred, max_split), 1)

        candidate_splits = sorted(
            range(min_train, max_split + 1),
            key=lambda split: abs(split - preferred),
        )
        for split in candidate_splits:
            train_target = frame.iloc[:split][target_column]
            test_target = frame.iloc[split:][target_column]
            if train_target.nunique() >= 2 and test_target.nunique() >= 2:
                return split
        for split in candidate_splits:
            train_target = frame.iloc[:split][target_column]
            if train_target.nunique() >= 2:
                return split
        return max(min(preferred, max_split), 1)

    def _artifact_dir(self, run_id: str) -> Path:
        return self.settings.data_dir / "research" / "shadow_runs" / run_id

    def _start_experiment_run(
        self,
        run_id: str,
        *,
        experiment_name: str,
        hypothesis: str,
        config_payload: dict[str, object],
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            session.add(
                ExperimentRun(
                    run_id=run_id,
                    experiment_name=experiment_name,
                    hypothesis=hypothesis,
                    config_json=orjson.dumps(config_payload).decode(),
                    status="running",
                    started_at=now,
                    created_at=now,
                )
            )
            session.commit()
        finally:
            session.close()

    def _record_label_program_metrics(
        self,
        run_id: str,
        candidate_report: dict[str, object],
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            rows = [
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="label_program_auto_promotion_eligible",
                    metric_value=1.0 if candidate_report["auto_promotion_eligible"] else 0.0,
                    metric_metadata=None,
                    recorded_at=now,
                ),
            ]
            for family_name, family_metrics in (candidate_report["families"] or {}).items():
                for metric_name in (
                    "rows_total",
                    "valid_rows",
                    "valid_coverage",
                    "invalid_rate",
                    "low_confidence_rate",
                    "normalized_class_entropy",
                ):
                    value = family_metrics.get(metric_name)
                    if value is None:
                        continue
                    rows.append(
                        ExperimentMetric(
                            experiment_run_id=run_id,
                            metric_name=f"{family_name}_{metric_name}",
                            metric_value=float(value),
                            metric_metadata=None,
                            recorded_at=now,
                        )
                    )
            session.add_all(rows)
            session.commit()
        finally:
            session.close()

    def _record_strategy_eval_metrics(
        self,
        run_id: str,
        challenger_report: dict[str, object],
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            rows = [
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="strategy_eval_auto_promotion_eligible",
                    metric_value=1.0 if challenger_report["auto_promotion_eligible"] else 0.0,
                    metric_metadata=None,
                    recorded_at=now,
                ),
            ]
            for family_name, family_metrics in (challenger_report["families"] or {}).items():
                for metric_name in (
                    "rows_total",
                    "rows_train",
                    "rows_test",
                    "rf_accuracy",
                    "rf_auc",
                    "xgb_accuracy",
                    "xgb_auc",
                    "positive_expectancy",
                ):
                    value = family_metrics.get(metric_name)
                    if value is None:
                        continue
                    rows.append(
                        ExperimentMetric(
                            experiment_run_id=run_id,
                            metric_name=f"{family_name}_{metric_name}",
                            metric_value=float(value),
                            metric_metadata=None,
                            recorded_at=now,
                        )
                    )
            session.add_all(rows)
            session.commit()
        finally:
            session.close()

    def _finish_experiment_run(self, run_id: str, *, status: str, conclusion: str) -> None:
        session = get_session(self.settings)
        try:
            run = session.query(ExperimentRun).filter_by(run_id=run_id).first()
            if run is None:
                return
            run.status = status
            run.finished_at = utcnow()
            run.conclusion = conclusion
            session.commit()
        finally:
            session.close()

    def _record_experiment_metrics(
        self,
        run_id: str,
        chronos_summary: dict[str, object],
        model_metrics: dict[str, object],
        dataset: pd.DataFrame,
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            rows = [
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="dataset_rows",
                    metric_value=float(len(dataset)),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="anomaly_rate",
                    metric_value=float(model_metrics["anomaly_rate"]),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="chronos_available",
                    metric_value=1.0 if chronos_summary["status"] == "ok" else 0.0,
                    metric_metadata=chronos_summary["status"],
                    recorded_at=now,
                ),
            ]
            for family_name, family_metrics in model_metrics["families"].items():
                for metric_name, value in family_metrics.items():
                    if value is None:
                        continue
                    rows.append(
                        ExperimentMetric(
                            experiment_run_id=run_id,
                            metric_name=f"{family_name}_{metric_name}",
                            metric_value=float(value),
                            metric_metadata=None,
                            recorded_at=now,
                        )
                    )
            session.add_all(rows)
            session.commit()
        finally:
            session.close()

    def _write_shadow_artifacts(
        self,
        *,
        run_id: str,
        artifact_dir: Path,
        config_payload: dict[str, object],
        chronos_summary: dict[str, object],
        model_metrics: dict[str, object],
        dataset: pd.DataFrame,
    ) -> None:
        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="shadow_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "chronos_summary.json",
            chronos_summary,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="shadow_chronos_summary",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "model_metrics.json",
            model_metrics,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="shadow_model_metrics",
            settings=self.settings,
        )
        dataset_preview = self._json_ready_dataset_preview(dataset)
        write_json_artifact(
            artifact_dir / "dataset_preview.json",
            dataset_preview,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="shadow_dataset_preview",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            self._render_report_qmd(config_payload, chronos_summary, model_metrics),
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="shadow_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

    def _write_label_program_artifacts(
        self,
        *,
        run_id: str,
        artifact_dir: Path,
        config_payload: dict[str, object],
        candidate_report: dict[str, object],
        dataset: pd.DataFrame,
    ) -> None:
        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="label_program_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "label_program_candidate.json",
            candidate_report,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="label_program_candidate",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "dataset_preview.json",
            self._json_ready_dataset_preview(dataset),
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="label_program_dataset_preview",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            self._render_label_program_report_qmd(config_payload, candidate_report),
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="label_program_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

    def _write_strategy_eval_artifacts(
        self,
        *,
        run_id: str,
        artifact_dir: Path,
        config_payload: dict[str, object],
        challenger_report: dict[str, object],
        dataset: pd.DataFrame,
    ) -> None:
        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="strategy_eval_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "strategy_challenger_report.json",
            challenger_report,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="strategy_challenger_report",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "dataset_preview.json",
            self._json_ready_dataset_preview(dataset),
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="strategy_eval_dataset_preview",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            self._render_strategy_eval_report_qmd(config_payload, challenger_report),
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="strategy_eval_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

    def _write_dropbox_research_artifact(
        self,
        filename: str,
        payload: dict[str, object],
        *,
        owner_key: str,
    ) -> Path:
        output_path = self.repo_root / ".ai" / "dropbox" / "research" / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_artifact(
            output_path,
            payload,
            owner_type="experiment_run",
            owner_key=owner_key,
            artifact_type="dropbox_research_copy",
            settings=self.settings,
        )
        return output_path

    def _json_ready_dataset_preview(self, dataset: pd.DataFrame) -> list[dict[str, object]]:
        preview = dataset.tail(50).copy()
        for column in preview.columns:
            if pd.api.types.is_datetime64_any_dtype(preview[column]):
                preview[column] = preview[column].apply(
                    lambda value: value.isoformat() if pd.notna(value) else None
                )
        preview = preview.where(pd.notna(preview), None)
        return preview.to_dict(orient="records")

    def _render_report_qmd(
        self,
        config_payload: dict[str, object],
        chronos_summary: dict[str, object],
        model_metrics: dict[str, object],
    ) -> str:
        family_lines = [
            (
                f"- `{family}`: rf_acc={metrics['rf_accuracy']:.3f}, "
                f"rf_auc={metrics['rf_auc']}, "
                f"xgb_acc={metrics['xgb_accuracy']:.3f}, "
                f"xgb_auc={metrics['xgb_auc']}"
            )
            for family, metrics in sorted(model_metrics["families"].items())
        ]
        if not family_lines:
            family_lines = ["- no evaluable label families"]

        chronos_lines = [f"- status: `{chronos_summary['status']}`"]
        if chronos_summary.get("anchor_product_id"):
            chronos_lines.append(f"- anchor product: `{chronos_summary['anchor_product_id']}`")
        if chronos_summary.get("fibonacci"):
            chronos_lines.append(
                f"- confluence: `{chronos_summary['fibonacci']['confluence']}`"
            )

        return render_qmd(
            "experiment_run.qmd",
            title=str(config_payload["shadow_run"]),
            summary_lines=[
                f"- spot feature run: `{config_payload['spot_feature_run_id']}`",
                f"- regime feature run: `{config_payload['regime_feature_run_id']}`",
                f"- regime model: `{config_payload['regime_model_family']}`",
                f"- macro context: `{config_payload['macro_context_state']}`",
                f"- runtime-adjacent models: `{sorted(RUNTIME_ADJACENT_MODELS)}`",
                f"- shadow-only models: `{sorted(SHADOW_ONLY_MODELS)}`",
            ],
            sections=[
                ("Chronos and Monte Carlo", chronos_lines),
                ("Meta-Model Metrics", family_lines),
            ],
        )

    def _render_label_program_report_qmd(
        self,
        config_payload: dict[str, object],
        candidate_report: dict[str, object],
    ) -> str:
        family_lines: list[str] = []
        for family_name, metrics in sorted((candidate_report.get("families") or {}).items()):
            family_lines.extend(
                [
                    f"## {family_name}",
                    "",
                    f"- rows total: `{metrics['rows_total']}`",
                    f"- valid coverage: `{metrics['valid_coverage']:.3f}`",
                    f"- invalid rate: `{metrics['invalid_rate']:.3f}`",
                    f"- low confidence rate: `{metrics['low_confidence_rate']:.3f}`",
                    f"- normalized entropy: `{metrics['normalized_class_entropy']:.3f}`",
                    f"- eligible: `{metrics['eligible']}`",
                    "",
                ]
            )

        return render_qmd(
            "experiment_run.qmd",
            title=str(config_payload["label_program"]),
            summary_lines=[
                f"- spot feature run: `{config_payload['spot_feature_run_id']}`",
                f"- regime feature run: `{config_payload['regime_feature_run_id']}`",
                f"- auto-promotion eligible: `{candidate_report['auto_promotion_eligible']}`",
                "- runtime effect: `proposal_only`",
            ],
            sections=[
                (
                    "Canonical Label Program Summary",
                    family_lines or ["- no label families"],
                )
            ],
        )

    def _render_strategy_eval_report_qmd(
        self,
        config_payload: dict[str, object],
        challenger_report: dict[str, object],
    ) -> str:
        family_lines: list[str] = []
        for family_name, metrics in sorted((challenger_report.get("families") or {}).items()):
            family_lines.extend(
                [
                    f"## {family_name}",
                    "",
                    f"- label family: `{metrics['label_family']}`",
                    f"- target label: `{metrics['target_label']}`",
                    f"- rows total: `{metrics['rows_total']}`",
                    f"- rf accuracy: `{metrics['rf_accuracy']:.3f}`",
                    f"- xgb accuracy: `{metrics['xgb_accuracy']:.3f}`",
                    f"- xgb auc: `{metrics['xgb_auc']}`",
                    f"- positive expectancy: `{metrics['positive_expectancy']}`",
                    f"- eligible: `{metrics['eligible']}`",
                    "",
                ]
            )

        return render_qmd(
            "experiment_run.qmd",
            title=str(config_payload["strategy_eval"]),
            summary_lines=[
                f"- spot feature run: `{config_payload['spot_feature_run_id']}`",
                f"- regime feature run: `{config_payload['regime_feature_run_id']}`",
                f"- top family: `{challenger_report.get('top_family') or 'none'}`",
                f"- auto-promotion eligible: `{challenger_report['auto_promotion_eligible']}`",
                "- runtime effect: `proposal_only`",
            ],
            sections=[
                (
                    "Strategy Challenger Summary",
                    family_lines or ["- no strategy families"],
                )
            ],
        )
