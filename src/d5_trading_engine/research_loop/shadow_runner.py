"""Shadow-mode evaluation for the intraday meta-stack."""

from __future__ import annotations

import math
import uuid
from pathlib import Path

import numpy as np
import orjson
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score
from xgboost import XGBClassifier

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.condition.scorer import (
    _REFIT_CADENCE_BUCKETS,
    _TRAINING_WINDOW,
    ConditionScorer,
)
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.features.materializer import _FEATURE_SET_NAME
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


class ShadowRunner:
    """Run bounded shadow evaluations from canonical truth and condition history."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def run_intraday_meta_stack_v1(self) -> dict[str, object]:
        """Run the shadow meta-stack and persist experiment receipts."""
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

        label_frame = self._attach_triple_barrier_labels(market_bars_5m)
        dataset = self._build_meta_dataset(spot_frame, regime_result.history, label_frame)
        if len(dataset) < _MIN_DATASET_ROWS:
            raise RuntimeError(
                f"Need at least {_MIN_DATASET_ROWS} joined rows for shadow evaluation; "
                f"found {len(dataset)}."
            )

        run_id = f"experiment_{_SHADOW_RUN_NAME}_{uuid.uuid4().hex[:12]}"
        artifact_dir = self._artifact_dir(run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)

        config_payload = {
            "shadow_run": _SHADOW_RUN_NAME,
            "spot_feature_run_id": spot_feature_run.run_id,
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
        }
        self._start_experiment_run(run_id, config_payload)

        try:
            chronos_summary = self._run_chronos_and_monte_carlo(dataset, market_bars_5m)
            model_metrics = self._run_meta_models(dataset)
            if not model_metrics["families"]:
                raise RuntimeError("Shadow models did not produce any evaluable label families.")

            self._write_shadow_artifacts(
                artifact_dir=artifact_dir,
                config_payload=config_payload,
                chronos_summary=chronos_summary,
                model_metrics=model_metrics,
                dataset=dataset,
            )
            self._record_experiment_metrics(run_id, chronos_summary, model_metrics, dataset)

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

    def _load_market_bars(self, product_ids: list[str], *, bucket_minutes: int) -> pd.DataFrame:
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
            lambda series: series.rolling(_ATR_WINDOW, min_periods=5).mean()
        )
        grouped.rename(columns={bucket_label: "bucket_start_utc"}, inplace=True)
        return grouped

    def _attach_triple_barrier_labels(self, bars: pd.DataFrame) -> pd.DataFrame:
        labeled = bars.copy()
        for label_name, horizon_bars in _LABEL_SPECS.items():
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
        isolation_forest = IsolationForest(
            contamination=0.08,
            n_estimators=100,
            random_state=42,
        )
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

            rf = RandomForestClassifier(
                n_estimators=120,
                min_samples_leaf=2,
                random_state=42,
            )
            rf.fit(train_matrix, y_train)
            rf_probs = rf.predict_proba(test_matrix)[:, 1]
            rf_preds = (rf_probs >= 0.5).astype(int)

            xgb = XGBClassifier(
                n_estimators=80,
                max_depth=3,
                learning_rate=0.1,
                subsample=0.9,
                colsample_bytree=0.9,
                tree_method="hist",
                eval_metric="logloss",
                random_state=42,
            )
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

    def _artifact_dir(self, run_id: str) -> Path:
        return self.settings.data_dir / "research" / "shadow_runs" / run_id

    def _start_experiment_run(self, run_id: str, config_payload: dict[str, object]) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            session.add(
                ExperimentRun(
                    run_id=run_id,
                    experiment_name=_SHADOW_RUN_NAME,
                    hypothesis=(
                        "HMM-aligned regimes plus anomaly veto should improve the "
                        "expected value of short-horizon crypto setups."
                    ),
                    config_json=orjson.dumps(config_payload).decode(),
                    status="running",
                    started_at=now,
                    created_at=now,
                )
            )
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
        artifact_dir: Path,
        config_payload: dict[str, object],
        chronos_summary: dict[str, object],
        model_metrics: dict[str, object],
        dataset: pd.DataFrame,
    ) -> None:
        json_options = orjson.OPT_INDENT_2 | orjson.OPT_SERIALIZE_NUMPY
        (artifact_dir / "config.json").write_bytes(
            orjson.dumps(config_payload, option=json_options)
        )
        (artifact_dir / "chronos_summary.json").write_bytes(
            orjson.dumps(chronos_summary, option=json_options)
        )
        (artifact_dir / "model_metrics.json").write_bytes(
            orjson.dumps(model_metrics, option=json_options)
        )
        dataset_preview = self._json_ready_dataset_preview(dataset)
        (artifact_dir / "dataset_preview.json").write_bytes(
            orjson.dumps(dataset_preview, option=json_options)
        )
        (artifact_dir / "report.qmd").write_text(
            self._render_report_qmd(config_payload, chronos_summary, model_metrics),
            encoding="utf-8",
        )

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

        return "\n".join(
            [
                "---",
                f"title: {config_payload['shadow_run']}",
                f"date: {utcnow().isoformat()}",
                "format: gfm",
                "---",
                "",
                "# Shadow Summary",
                "",
                f"- spot feature run: `{config_payload['spot_feature_run_id']}`",
                f"- regime feature run: `{config_payload['regime_feature_run_id']}`",
                f"- regime model: `{config_payload['regime_model_family']}`",
                f"- macro context: `{config_payload['macro_context_state']}`",
                "",
                "# Chronos and Monte Carlo",
                "",
                *chronos_lines,
                "",
                "# Meta-Model Metrics",
                "",
                *family_lines,
            ]
        )
