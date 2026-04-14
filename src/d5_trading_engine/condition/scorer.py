"""Condition scoring backed by bounded global-regime inputs."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta

import orjson
import pandas as pd
from sklearn.mixture import GaussianMixture

from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.features.materializer import _GLOBAL_REGIME_FEATURE_SET_NAME
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ConditionGlobalRegimeSnapshotV1,
    ConditionScoringRun,
    FeatureGlobalRegimeInput15mV1,
    FeatureMaterializationRun,
)

log = get_logger(__name__)

_CONDITION_SET_NAME = "global_regime_v1"
_TRAINING_WINDOW = timedelta(days=90)
_MIN_TRAIN_ROWS = 32
_N_COMPONENTS = 4
_CONFIDENCE_DEGRADE_FACTOR = 0.75
_BLOCKED_REGIMES = {"risk_off", "no_trade"}
_NUMERIC_FEATURE_COLUMNS = [
    "market_return_mean_15m",
    "market_return_std_15m",
    "market_realized_vol_15m",
    "market_volume_sum_15m",
    "market_trade_count_15m",
    "market_trade_size_sum_15m",
    "market_book_spread_bps_mean_15m",
    "market_return_mean_4h",
    "market_realized_vol_4h",
    "fred_dff",
    "fred_t10y2y",
    "fred_vixcls",
    "fred_dgs10",
    "fred_dtwexbgs",
]


@dataclass
class RegimeHistoryResult:
    """Model fit outputs used by the latest snapshot and shadow evaluation."""

    feature_run_id: str
    history: pd.DataFrame
    state_semantics: dict[int, dict[str, object]]
    model_family: str
    macro_context_state: str
    training_window_start_utc: object
    training_window_end_utc: object


class ConditionScorer:
    """Market condition scorer backed by canonical regime inputs."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def score_current(self) -> dict:
        """Score the current market conditions from the latest regime input run."""
        snapshot = self.score_global_regime_v1()
        latest = snapshot["latest_snapshot"]
        history = snapshot["history"]
        latest_row = history.iloc[-1]

        volatility_regime = "high" if (
            float(latest_row["market_realized_vol_15m"] or 0.0)
            >= float(history["market_realized_vol_15m"].median(skipna=True) or 0.0)
        ) else "normal"
        spread = float(latest_row["market_book_spread_bps_mean_15m"] or 0.0)
        trade_count = float(latest_row["market_trade_count_15m"] or 0.0)
        liquidity_score = None if spread <= 0 else round(trade_count / spread, 6)

        return {
            "regime": latest["semantic_regime"],
            "volatility_regime": volatility_regime,
            "liquidity_score": liquidity_score,
            "macro_score": latest_row["macro_context_available"],
            "confidence": latest["confidence"],
            "blocked": latest["blocked"],
            "blocking_reason": latest["blocking_reason"],
            "bucket_start_utc": latest["bucket_start_utc"],
            "model_family": snapshot["model_family"],
            "condition_set": _CONDITION_SET_NAME,
            "is_scaffold": False,
        }

    def score_global_regime_v1(self) -> dict[str, object]:
        """Fit the bounded regime model and persist the latest snapshot."""
        result = self.build_regime_history()
        run_id = f"condition_{_CONDITION_SET_NAME}_{uuid.uuid4().hex[:12]}"
        latest = result.history.iloc[-1]
        confidence = float(latest["confidence"])
        semantic_regime = str(latest["semantic_regime"])
        blocked = 1 if semantic_regime in _BLOCKED_REGIMES else 0
        blocking_reason = semantic_regime if blocked else None

        self._start_run(
            run_id=run_id,
            source_feature_run_id=result.feature_run_id,
            model_family=result.model_family,
            training_window_start_utc=result.training_window_start_utc,
            training_window_end_utc=result.training_window_end_utc,
            scored_bucket_start_utc=latest["bucket_start_utc"],
            state_semantics=result.state_semantics,
        )
        try:
            session = get_session(self.settings)
            try:
                session.add(
                    ConditionGlobalRegimeSnapshotV1(
                        condition_run_id=run_id,
                        source_feature_run_id=result.feature_run_id,
                        bucket_start_utc=latest["bucket_start_utc"].to_pydatetime(),
                        raw_state_id=int(latest["raw_state_id"]),
                        semantic_regime=semantic_regime,
                        confidence=confidence,
                        blocked_flag=blocked,
                        blocking_reason=blocking_reason,
                        model_family=result.model_family,
                        macro_context_state=result.macro_context_state,
                        created_at=utcnow(),
                    )
                )
                session.commit()
            finally:
                session.close()

            self._finish_run(
                run_id=run_id,
                status="success",
                confidence=confidence,
            )
        except Exception as exc:
            self._finish_run(run_id=run_id, status="failed", error=str(exc))
            raise

        return {
            "run_id": run_id,
            "model_family": result.model_family,
            "feature_run_id": result.feature_run_id,
            "latest_snapshot": {
                "bucket_start_utc": latest["bucket_start_utc"].isoformat(),
                "raw_state_id": int(latest["raw_state_id"]),
                "semantic_regime": semantic_regime,
                "confidence": confidence,
                "blocked": bool(blocked),
                "blocking_reason": blocking_reason,
                "macro_context_state": result.macro_context_state,
            },
            "history": result.history,
        }

    def build_regime_history(self) -> RegimeHistoryResult:
        """Build a scored regime history from the latest successful feature run."""
        feature_run = self._latest_feature_run()
        history = self._load_feature_history(feature_run.run_id)
        if history.empty:
            raise RuntimeError("No global regime input rows available for condition scoring.")

        latest_bucket = history["bucket_start_utc"].iloc[-1]
        training_start = latest_bucket - _TRAINING_WINDOW
        training_history = history.loc[history["bucket_start_utc"] >= training_start].copy()
        if len(training_history) < _MIN_TRAIN_ROWS:
            raise RuntimeError(
                f"Need at least {_MIN_TRAIN_ROWS} 15-minute rows for regime scoring; "
                f"found {len(training_history)}."
            )

        feature_matrix = self._prepare_feature_matrix(training_history)
        raw_states, probabilities, model_family = self._fit_regime_model(feature_matrix)
        training_history["raw_state_id"] = raw_states
        training_history["confidence"] = probabilities.max(axis=1)

        semantics = self._state_semantics(training_history)
        training_history["semantic_regime"] = training_history["raw_state_id"].map(
            lambda state_id: semantics[int(state_id)]["semantic_regime"]
        )

        macro_context_state = self._macro_context_state(feature_run)
        if macro_context_state != "healthy_recent":
            training_history["confidence"] = training_history["confidence"].apply(
                lambda value: max(0.0, min(1.0, float(value) * _CONFIDENCE_DEGRADE_FACTOR))
            )

        return RegimeHistoryResult(
            feature_run_id=feature_run.run_id,
            history=training_history,
            state_semantics=semantics,
            model_family=model_family,
            macro_context_state=macro_context_state,
            training_window_start_utc=training_history["bucket_start_utc"].iloc[0].to_pydatetime(),
            training_window_end_utc=training_history["bucket_start_utc"].iloc[-1].to_pydatetime(),
        )

    def _latest_feature_run(self) -> FeatureMaterializationRun:
        session = get_session(self.settings)
        try:
            run = (
                session.query(FeatureMaterializationRun)
                .filter_by(feature_set=_GLOBAL_REGIME_FEATURE_SET_NAME, status="success")
                .order_by(FeatureMaterializationRun.finished_at.desc())
                .first()
            )
            if run is None:
                raise RuntimeError(
                    "No successful global-regime input feature run exists. "
                    "Run `d5 materialize-features global-regime-inputs-15m-v1` first."
                )
            return run
        finally:
            session.close()

    def _load_feature_history(self, feature_run_id: str) -> pd.DataFrame:
        session = get_session(self.settings)
        try:
            rows = (
                session.query(FeatureGlobalRegimeInput15mV1)
                .filter_by(feature_run_id=feature_run_id)
                .order_by(FeatureGlobalRegimeInput15mV1.bucket_start_utc.asc())
                .all()
            )
        finally:
            session.close()

        frame = pd.DataFrame(
            [
                {
                    "bucket_start_utc": ensure_utc(row.bucket_start_utc),
                    "macro_context_available": int(row.macro_context_available or 0),
                    **{
                        column: getattr(row, column)
                        for column in _NUMERIC_FEATURE_COLUMNS
                    },
                }
                for row in rows
            ]
        )
        if frame.empty:
            return frame
        frame["bucket_start_utc"] = pd.to_datetime(frame["bucket_start_utc"], utc=True)
        return frame

    def _prepare_feature_matrix(self, history: pd.DataFrame):
        matrix = history[_NUMERIC_FEATURE_COLUMNS].copy()
        matrix = matrix.ffill().bfill().fillna(0.0)
        return matrix.to_numpy(dtype=float)

    def _fit_regime_model(self, feature_matrix):
        try:
            from hmmlearn.hmm import GaussianHMM
        except ModuleNotFoundError:
            model = GaussianMixture(
                n_components=_N_COMPONENTS,
                covariance_type="diag",
                n_init=5,
                random_state=42,
            )
            model.fit(feature_matrix)
            return (
                model.predict(feature_matrix),
                model.predict_proba(feature_matrix),
                "gaussian_mixture_regime_proxy_4state",
            )

        model = GaussianHMM(
            n_components=_N_COMPONENTS,
            covariance_type="diag",
            n_iter=200,
            random_state=42,
        )
        model.fit(feature_matrix)
        return (
            model.predict(feature_matrix),
            model.predict_proba(feature_matrix),
            "gaussian_hmm_4state",
        )

    def _state_semantics(self, history: pd.DataFrame) -> dict[int, dict[str, object]]:
        summaries: dict[int, dict[str, object]] = {}
        for state_id in sorted(history["raw_state_id"].unique()):
            state_rows = history.loc[history["raw_state_id"] == state_id]
            summaries[int(state_id)] = {
                "rows": int(len(state_rows)),
                "return_mean": float(state_rows["market_return_mean_15m"].mean(skipna=True) or 0.0),
                "vol_mean": float(state_rows["market_realized_vol_15m"].mean(skipna=True) or 0.0),
                "spread_mean": float(
                    state_rows["market_book_spread_bps_mean_15m"].mean(skipna=True) or 0.0
                ),
            }

        remaining = list(summaries)
        if not remaining:
            raise RuntimeError("No latent states were produced for regime scoring.")

        risk_off_state = max(
            remaining,
            key=lambda state_id: (
                summaries[state_id]["vol_mean"],
                summaries[state_id]["spread_mean"],
            ),
        )
        summaries[risk_off_state]["semantic_regime"] = "risk_off"
        remaining.remove(risk_off_state)

        if remaining:
            long_state = max(remaining, key=lambda state_id: summaries[state_id]["return_mean"])
            summaries[long_state]["semantic_regime"] = "long_friendly"
            remaining.remove(long_state)

        if remaining:
            short_state = min(remaining, key=lambda state_id: summaries[state_id]["return_mean"])
            summaries[short_state]["semantic_regime"] = "short_friendly"
            remaining.remove(short_state)

        for state_id in remaining:
            summaries[state_id]["semantic_regime"] = "no_trade"

        return summaries

    def _macro_context_state(self, feature_run: FeatureMaterializationRun) -> str:
        if not feature_run.freshness_snapshot_json:
            return "missing"
        snapshot = orjson.loads(feature_run.freshness_snapshot_json)
        lanes = snapshot.get("required_lanes", {})
        macro_lane = lanes.get("fred-observations")
        if not macro_lane:
            return "missing"
        return str(macro_lane.get("freshness_state", "missing"))

    def _start_run(
        self,
        *,
        run_id: str,
        source_feature_run_id: str,
        model_family: str,
        training_window_start_utc,
        training_window_end_utc,
        scored_bucket_start_utc,
        state_semantics: dict[int, dict[str, object]],
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            session.add(
                ConditionScoringRun(
                    run_id=run_id,
                    condition_set=_CONDITION_SET_NAME,
                    source_feature_run_id=source_feature_run_id,
                    model_family=model_family,
                    training_window_start_utc=ensure_utc(training_window_start_utc),
                    training_window_end_utc=ensure_utc(training_window_end_utc),
                    scored_bucket_start_utc=ensure_utc(scored_bucket_start_utc),
                    state_semantics_json=orjson.dumps(
                        {str(key): value for key, value in state_semantics.items()}
                    ).decode(),
                    model_params_json=orjson.dumps(
                        {
                            "n_components": _N_COMPONENTS,
                            "min_train_rows": _MIN_TRAIN_ROWS,
                            "training_window_days": _TRAINING_WINDOW.days,
                        }
                    ).decode(),
                    status="running",
                    started_at=now,
                    created_at=now,
                )
            )
            session.commit()
        finally:
            session.close()

    def _finish_run(
        self,
        *,
        run_id: str,
        status: str,
        confidence: float | None = None,
        error: str | None = None,
    ) -> None:
        session = get_session(self.settings)
        try:
            run = session.query(ConditionScoringRun).filter_by(run_id=run_id).first()
            if run is None:
                return
            run.status = status
            run.confidence = confidence
            run.error_message = error
            run.finished_at = utcnow()
            session.commit()
        finally:
            session.close()
