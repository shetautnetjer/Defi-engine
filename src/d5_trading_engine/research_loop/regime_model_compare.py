"""Shadow-only comparison of bounded regime model candidates."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import pandas as pd
from sqlalchemy import func

from d5_trading_engine.common.time_utils import ensure_utc, utcnow
from d5_trading_engine.condition.scorer import (
    _CONFIDENCE_DEGRADE_FACTOR,
    ConditionScorer,
)
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.models.hmm_regime import (
    fit_gaussian_hmm,
    fit_gaussian_mixture_regime_proxy,
    hmmlearn_available,
    map_regime_state_semantics,
    predict_regime_states,
)
from d5_trading_engine.models.statsmodels_regime import (
    filter_markov_regression,
    fit_markov_regression,
    markov_log_likelihood,
    predict_markov_regime_states,
    statsmodels_regime_available,
)
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.proposals import create_improvement_proposal
from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import (
    ExperimentMetric,
    ExperimentRun,
    MarketCandle,
)

_COMPARE_RUN_NAME = "regime_model_compare_v1"
_TRAIN_WINDOW_BUCKETS = 64
_MIN_COMPARE_ROWS = 80
_REFIT_CADENCE_BUCKETS = 4
_N_COMPONENTS = 4
_CANDIDATE_ORDER = ("hmm", "gmm", "statsmodels")
_SEMANTIC_REGIMES = ("risk_off", "long_friendly", "short_friendly", "no_trade")


@dataclass
class _CandidateOutcome:
    """Shadow comparison result for one model family."""

    key: str
    model_family: str
    available: bool
    fit_success: bool
    fit_seconds: float
    prediction_rows: int
    state_count: int
    mean_confidence: float
    adjacent_flip_rate: float
    semantic_mapping_coverage: float
    fail_closed: bool
    log_likelihood: float | None
    error: str | None
    scored_history: list[dict[str, Any]]

    @property
    def semantic_shares(self) -> dict[str, float]:
        if not self.scored_history:
            return {regime: 0.0 for regime in _SEMANTIC_REGIMES}
        counts = {regime: 0 for regime in _SEMANTIC_REGIMES}
        for row in self.scored_history:
            regime = str(row.get("semantic_regime") or "")
            if regime in counts:
                counts[regime] += 1
        total = float(len(self.scored_history))
        return {regime: counts[regime] / total for regime in _SEMANTIC_REGIMES}

    def metric_payload(self) -> dict[str, float]:
        payload = {
            "available": 1.0 if self.available else 0.0,
            "fit_success": 1.0 if self.fit_success else 0.0,
            "fit_seconds": float(self.fit_seconds),
            "prediction_rows": float(self.prediction_rows),
            "state_count": float(self.state_count),
            "mean_confidence": float(self.mean_confidence),
            "adjacent_flip_rate": float(self.adjacent_flip_rate),
            "semantic_mapping_coverage": float(self.semantic_mapping_coverage),
            "fail_closed": 1.0 if self.fail_closed else 0.0,
        }
        for regime, share in self.semantic_shares.items():
            payload[f"{regime}_share"] = float(share)
        if self.log_likelihood is not None:
            payload["log_likelihood"] = float(self.log_likelihood)
        return payload


class RegimeModelComparator:
    """Compare bounded regime candidates on the existing 15-minute feature truth."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._scorer = ConditionScorer(self.settings)

    def run_regime_model_compare_v1(
        self,
        *,
        history_start: str | None = None,
        history_end: str | None = None,
        use_massive_context: bool = True,
        refit_cadence_buckets: int | None = None,
    ) -> dict[str, Any]:
        resolved_refit_cadence_buckets = max(
            1,
            int(
                refit_cadence_buckets
                if refit_cadence_buckets is not None
                else self.settings.regime_compare_refit_cadence_buckets
            ),
        )
        feature_run = self._scorer._latest_feature_run()
        history = self._scorer._load_feature_history(feature_run.run_id)
        history = self._filter_history(
            history,
            history_start=history_start,
            history_end=history_end,
            use_massive_context=use_massive_context,
        )
        if refit_cadence_buckets is None:
            max_refits = int(self.settings.regime_compare_max_refits)
            if max_refits > 0:
                scorable_buckets = max(len(history) - _TRAIN_WINDOW_BUCKETS, 1)
                resolved_refit_cadence_buckets = max(
                    resolved_refit_cadence_buckets,
                    (scorable_buckets + max_refits - 1) // max_refits,
                )
        macro_context_state = self._scorer._macro_context_state(feature_run)
        history_inventory = self._build_history_inventory(feature_run.run_id, history)

        run_id = f"experiment_{_COMPARE_RUN_NAME}_{uuid.uuid4().hex[:12]}"
        artifact_dir = self.settings.data_dir / "research" / "regime_model_compare" / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)

        config_payload = {
            "run_id": run_id,
            "shadow_run": _COMPARE_RUN_NAME,
            "feature_run_id": feature_run.run_id,
            "feature_set": feature_run.feature_set,
            "macro_context_state": macro_context_state,
            "feature_bucket_rows": int(len(history)),
            "min_compare_rows": _MIN_COMPARE_ROWS,
            "train_window_buckets": _TRAIN_WINDOW_BUCKETS,
            "refit_cadence_buckets": resolved_refit_cadence_buckets,
            "history_start": history_start,
            "history_end": history_end,
            "use_massive_context": bool(use_massive_context),
            "candidates": list(_CANDIDATE_ORDER),
            "artifact_dir": str(artifact_dir),
            "runtime_authority": "unchanged",
        }
        self._start_experiment_run(
            run_id,
            experiment_name=_COMPARE_RUN_NAME,
            hypothesis=(
                "A statsmodels Markov-switching candidate may provide a useful "
                "shadow comparison against the current HMM/GMM regime owner without "
                "widening live, policy, or risk behavior."
            ),
            config_payload=config_payload,
        )

        candidate_results: dict[str, _CandidateOutcome] = {}
        recommendation_payload: dict[str, Any] | None = None
        try:
            if len(history) < _MIN_COMPARE_ROWS:
                raise RuntimeError(
                    f"Need at least {_MIN_COMPARE_ROWS} 15-minute rows for regime comparison; "
                    f"found {len(history)}."
                )

            candidate_results = {
                "hmm": self._run_hmm_candidate(
                    history,
                    macro_context_state,
                    refit_cadence_buckets=resolved_refit_cadence_buckets,
                ),
                "gmm": self._run_gmm_candidate(
                    history,
                    macro_context_state,
                    refit_cadence_buckets=resolved_refit_cadence_buckets,
                ),
                "statsmodels": self._run_statsmodels_candidate(
                    history,
                    macro_context_state,
                    refit_cadence_buckets=resolved_refit_cadence_buckets,
                ),
            }
            if not any(result.fit_success for result in candidate_results.values()):
                raise RuntimeError("No regime candidates produced a successful shadow comparison.")

            recommendation_payload = self._recommend_follow_on(
                candidate_results=candidate_results,
                history_inventory=history_inventory,
            )
            comparison_payload = self._comparison_payload(
                run_id=run_id,
                config_payload=config_payload,
                history_inventory=history_inventory,
                candidate_results=candidate_results,
                recommendation_payload=recommendation_payload,
                status="success",
                error_message=None,
            )
            self._write_artifacts(
                run_id=run_id,
                artifact_dir=artifact_dir,
                config_payload=config_payload,
                history_inventory=history_inventory,
                comparison_payload=comparison_payload,
            )
            self._record_metrics(
                run_id=run_id,
                history=history,
                history_inventory=history_inventory,
                candidate_results=candidate_results,
            )
            proposal = create_improvement_proposal(
                artifact_dir=artifact_dir,
                proposal_kind="regime_model_compare_follow_on",
                source_owner_type="experiment_run",
                source_owner_key=run_id,
                governance_scope="research_loop",
                title="Regime model comparison follow-on",
                summary=str(recommendation_payload["summary"]),
                hypothesis=(
                    "Shadow comparison on existing 15-minute feature truth should guide "
                    "whether to extend statsmodels evaluation or keep the current "
                    "regime scorer unchanged."
                ),
                next_test=str(recommendation_payload["next_test"]),
                metrics=recommendation_payload["proposal_metrics"],
                reason_codes=list(recommendation_payload["reason_codes"]),
                settings=self.settings,
            )
            conclusion = (
                f"Regime comparison complete. "
                f"recommended={recommendation_payload['recommended_candidate']} "
                f"proposal={proposal['status']}"
            )
            self._finish_experiment_run(run_id, status="success", conclusion=conclusion)
            return {
                "run_id": run_id,
                "artifact_dir": str(artifact_dir),
                "recommended_candidate": recommendation_payload["recommended_candidate"],
                "proposal_id": proposal["proposal_id"],
                "proposal_status": proposal["status"],
            }
        except Exception as exc:
            comparison_payload = self._comparison_payload(
                run_id=run_id,
                config_payload=config_payload,
                history_inventory=history_inventory,
                candidate_results=candidate_results,
                recommendation_payload=recommendation_payload,
                status="failed",
                error_message=str(exc),
            )
            self._write_artifacts(
                run_id=run_id,
                artifact_dir=artifact_dir,
                config_payload=config_payload,
                history_inventory=history_inventory,
                comparison_payload=comparison_payload,
            )
            self._finish_experiment_run(run_id, status="failed", conclusion=str(exc))
            raise

    def _run_hmm_candidate(
        self,
        history: pd.DataFrame,
        macro_context_state: str,
        *,
        refit_cadence_buckets: int,
    ) -> _CandidateOutcome:
        if not hmmlearn_available():
            return self._unavailable_candidate(
                "hmm",
                "gaussian_hmm_4state",
                "optional hmmlearn dependency missing",
            )
        return self._run_feature_matrix_candidate(
            candidate_key="hmm",
            history=history,
            macro_context_state=macro_context_state,
            fit_fn=fit_gaussian_hmm,
            refit_cadence_buckets=refit_cadence_buckets,
        )

    def _run_gmm_candidate(
        self,
        history: pd.DataFrame,
        macro_context_state: str,
        *,
        refit_cadence_buckets: int,
    ) -> _CandidateOutcome:
        return self._run_feature_matrix_candidate(
            candidate_key="gmm",
            history=history,
            macro_context_state=macro_context_state,
            fit_fn=fit_gaussian_mixture_regime_proxy,
            refit_cadence_buckets=refit_cadence_buckets,
        )

    def _run_statsmodels_candidate(
        self,
        history: pd.DataFrame,
        macro_context_state: str,
        *,
        refit_cadence_buckets: int,
    ) -> _CandidateOutcome:
        if not statsmodels_regime_available():
            return self._unavailable_candidate(
                "statsmodels",
                "statsmodels_markov_regression_4state",
                "optional statsmodels dependency missing",
            )

        fit_seconds: list[float] = []
        scored_rows: list[dict[str, Any]] = []
        current_params = None
        current_semantics: dict[int, dict[str, object]] | None = None
        current_model_family = f"statsmodels_markov_regression_{_N_COMPONENTS}state"
        scored_count = 0

        try:
            for row_index in range(_TRAIN_WINDOW_BUCKETS - 1, len(history)):
                training_history = history.iloc[
                    row_index - _TRAIN_WINDOW_BUCKETS + 1 : row_index + 1
                ].copy()

                if current_params is None or (scored_count % refit_cadence_buckets == 0):
                    start = time.perf_counter()
                    result, current_model_family = fit_markov_regression(
                        training_history["market_return_mean_15m"].to_numpy(dtype=float),
                        k_regimes=_N_COMPONENTS,
                    )
                    fit_seconds.append(time.perf_counter() - start)
                    current_params = getattr(result, "params")
                    raw_states, probabilities = predict_markov_regime_states(result)
                    current_semantics = self._state_semantics_from_predictions(
                        training_history,
                        raw_states=raw_states,
                        probabilities=probabilities,
                    )
                    log_likelihood = markov_log_likelihood(result)
                    score_states = raw_states
                    score_probabilities = probabilities
                else:
                    filtered = filter_markov_regression(
                        params=current_params,
                        endog=training_history["market_return_mean_15m"].to_numpy(dtype=float),
                        k_regimes=_N_COMPONENTS,
                    )
                    score_states, score_probabilities = predict_markov_regime_states(filtered)
                    log_likelihood = markov_log_likelihood(filtered)

                assert current_semantics is not None
                scored_rows.append(
                    self._score_row_payload(
                        history_row=training_history.iloc[-1],
                        raw_state_id=int(score_states[-1]),
                        confidence=float(score_probabilities[-1].max()),
                        semantic_regime=str(
                            current_semantics[int(score_states[-1])]["semantic_regime"]
                        ),
                        macro_context_state=macro_context_state,
                    )
                )
                scored_count += 1
        except Exception as exc:
            return _CandidateOutcome(
                key="statsmodels",
                model_family=current_model_family,
                available=True,
                fit_success=False,
                fit_seconds=float(sum(fit_seconds)),
                prediction_rows=0,
                state_count=0,
                mean_confidence=0.0,
                adjacent_flip_rate=1.0,
                semantic_mapping_coverage=0.0,
                fail_closed=True,
                log_likelihood=None,
                error=str(exc),
                scored_history=[],
            )

        return self._finalize_candidate(
            key="statsmodels",
            model_family=current_model_family,
            fit_seconds=sum(fit_seconds),
            scored_rows=scored_rows,
            log_likelihood=log_likelihood if "log_likelihood" in locals() else None,
        )

    def _run_feature_matrix_candidate(
        self,
        *,
        candidate_key: str,
        history: pd.DataFrame,
        macro_context_state: str,
        fit_fn,
        refit_cadence_buckets: int,
    ) -> _CandidateOutcome:
        fit_seconds: list[float] = []
        scored_rows: list[dict[str, Any]] = []
        current_model = None
        current_semantics: dict[int, dict[str, object]] | None = None
        current_model_family = ""

        try:
            row_index = _TRAIN_WINDOW_BUCKETS - 1
            while row_index < len(history):
                training_history = history.iloc[
                    row_index - _TRAIN_WINDOW_BUCKETS + 1 : row_index + 1
                ].copy()
                matrix = self._scorer._prepare_feature_matrix(training_history)
                start = time.perf_counter()
                current_model, current_model_family = fit_fn(
                    matrix,
                    n_components=_N_COMPONENTS,
                )
                fit_seconds.append(time.perf_counter() - start)
                raw_states, probabilities = predict_regime_states(current_model, matrix)
                current_semantics = self._state_semantics_from_predictions(
                    training_history,
                    raw_states=raw_states,
                    probabilities=probabilities,
                )

                assert current_model is not None
                assert current_semantics is not None
                next_refit_index = min(row_index + refit_cadence_buckets, len(history))
                current_rows = history.iloc[row_index:next_refit_index]
                row_matrix = self._scorer._prepare_feature_matrix(current_rows)
                score_states, score_probabilities = predict_regime_states(
                    current_model,
                    row_matrix,
                )
                for offset, history_row in enumerate(current_rows.itertuples(index=False)):
                    raw_state_id = int(score_states[offset])
                    scored_rows.append(
                        self._score_row_payload(
                            history_row=pd.Series(history_row._asdict()),
                            raw_state_id=raw_state_id,
                            confidence=float(score_probabilities[offset].max()),
                            semantic_regime=str(
                                current_semantics[raw_state_id]["semantic_regime"]
                            ),
                            macro_context_state=macro_context_state,
                        )
                    )
                row_index = next_refit_index
        except Exception as exc:
            return _CandidateOutcome(
                key=candidate_key,
                model_family=current_model_family or candidate_key,
                available=True,
                fit_success=False,
                fit_seconds=float(sum(fit_seconds)),
                prediction_rows=0,
                state_count=0,
                mean_confidence=0.0,
                adjacent_flip_rate=1.0,
                semantic_mapping_coverage=0.0,
                fail_closed=True,
                log_likelihood=None,
                error=str(exc),
                scored_history=[],
            )

        return self._finalize_candidate(
            key=candidate_key,
            model_family=current_model_family,
            fit_seconds=sum(fit_seconds),
            scored_rows=scored_rows,
            log_likelihood=None,
        )

    def _state_semantics_from_predictions(
        self,
        history: pd.DataFrame,
        *,
        raw_states,
        probabilities,
    ) -> dict[int, dict[str, object]]:
        semantic_history = history.copy()
        semantic_history["raw_state_id"] = np.asarray(raw_states, dtype=int)
        confidence = np.asarray(probabilities, dtype=float).max(axis=1)
        semantic_history["confidence"] = confidence
        return map_regime_state_semantics(semantic_history)

    def _score_row_payload(
        self,
        *,
        history_row: pd.Series,
        raw_state_id: int,
        confidence: float,
        semantic_regime: str,
        macro_context_state: str = "healthy_recent",
    ) -> dict[str, Any]:
        if macro_context_state != "healthy_recent":
            confidence = max(0.0, min(1.0, confidence * _CONFIDENCE_DEGRADE_FACTOR))
        bucket = ensure_utc(history_row["bucket_start_utc"])
        return {
            "bucket_start_utc": bucket.isoformat() if bucket is not None else "",
            "raw_state_id": raw_state_id,
            "confidence": float(confidence),
            "semantic_regime": semantic_regime,
        }

    def _finalize_candidate(
        self,
        *,
        key: str,
        model_family: str,
        fit_seconds: float,
        scored_rows: list[dict[str, Any]],
        log_likelihood: float | None,
    ) -> _CandidateOutcome:
        prediction_rows = len(scored_rows)
        if prediction_rows == 0:
            return _CandidateOutcome(
                key=key,
                model_family=model_family,
                available=True,
                fit_success=False,
                fit_seconds=float(fit_seconds),
                prediction_rows=0,
                state_count=0,
                mean_confidence=0.0,
                adjacent_flip_rate=1.0,
                semantic_mapping_coverage=0.0,
                fail_closed=True,
                log_likelihood=log_likelihood,
                error="no scored rows produced",
                scored_history=[],
            )

        raw_states = [int(row["raw_state_id"]) for row in scored_rows]
        semantic_regimes = [str(row["semantic_regime"]) for row in scored_rows]
        adjacent_flips = sum(
            1
            for idx in range(1, len(semantic_regimes))
            if semantic_regimes[idx] != semantic_regimes[idx - 1]
        )
        coverage = sum(1 for regime in semantic_regimes if regime in _SEMANTIC_REGIMES) / float(
            prediction_rows
        )
        return _CandidateOutcome(
            key=key,
            model_family=model_family,
            available=True,
            fit_success=True,
            fit_seconds=float(fit_seconds),
            prediction_rows=prediction_rows,
            state_count=len(set(raw_states)),
            mean_confidence=float(
                sum(float(row["confidence"]) for row in scored_rows) / prediction_rows
            ),
            adjacent_flip_rate=float(adjacent_flips / max(prediction_rows - 1, 1)),
            semantic_mapping_coverage=float(coverage),
            fail_closed=False,
            log_likelihood=log_likelihood,
            error=None,
            scored_history=scored_rows,
        )

    def _unavailable_candidate(
        self,
        key: str,
        model_family: str,
        reason: str,
    ) -> _CandidateOutcome:
        return _CandidateOutcome(
            key=key,
            model_family=model_family,
            available=False,
            fit_success=False,
            fit_seconds=0.0,
            prediction_rows=0,
            state_count=0,
            mean_confidence=0.0,
            adjacent_flip_rate=1.0,
            semantic_mapping_coverage=0.0,
            fail_closed=True,
            log_likelihood=None,
            error=reason,
            scored_history=[],
        )

    def _recommend_follow_on(
        self,
        *,
        candidate_results: dict[str, _CandidateOutcome],
        history_inventory: dict[str, Any],
    ) -> dict[str, Any]:
        successful = [result for result in candidate_results.values() if result.fit_success]
        best = max(
            successful,
            key=lambda result: (
                result.semantic_mapping_coverage,
                -result.adjacent_flip_rate,
                result.mean_confidence,
                result.prediction_rows,
            ),
        )
        feature_rows = int(history_inventory["feature_history"]["row_count"])
        massive_present = bool(history_inventory["massive_history"]["present"])

        reason_codes = [
            "feature_table_first_comparison",
            "proposal_only_follow_on",
        ]
        if not massive_present:
            reason_codes.append("massive_history_absent_in_current_sql")
        if feature_rows < 160:
            reason_codes.append("feature_history_short_for_regime_benchmark")

        if not candidate_results["statsmodels"].available:
            reason_codes.append("statsmodels_optional_dependency_missing")
            summary = (
                "The feature-table-first shadow comparison kept live, policy, and risk "
                "surfaces unchanged. "
                "statsmodels was unavailable in this environment, so the repo should keep the "
                "current runtime scorer unchanged and rerun the same comparison after the ML "
                "extra is installed."
            )
            next_test = (
                "Install the `ml` extra with statsmodels enabled, rerun "
                "`d5 run-shadow regime-model-compare-v1`, and compare the same feature-table "
                "benchmark before considering any runtime dependency swap."
            )
        elif feature_rows < 160:
            summary = (
                "The shadow comparison ran on the current 15-minute feature truth without "
                "changing live, policy, or risk surfaces, but the history remains short for a stronger "
                "regime-owner benchmark. Keep the current scorer unchanged and extend the "
                "comparison after a longer canonical history window is available."
            )
            next_test = (
                "Backfill more canonical market history, rerun "
                "`d5 materialize-features global-regime-inputs-15m-v1`, then rerun "
                "`d5 run-shadow regime-model-compare-v1 --use-massive-context` before revisiting regime-owner "
                "dependencies."
            )
        elif best.key == "statsmodels":
            reason_codes.append("statsmodels_shadow_candidate_promising")
            summary = (
                "The shadow comparison suggests the statsmodels candidate is promising on the "
                "current feature-truth benchmark, but the governed scorer should remain unchanged "
                "until the same comparison holds across a longer historical window."
            )
            next_test = (
                "Keep the current runtime scorer unchanged and extend the statsmodels candidate "
                "in shadow over a longer 15-minute feature history, then review the resulting "
                "experiment packet and proposal evidence."
            )
        else:
            reason_codes.append("current_runtime_regime_owner_remains_best_shadow_baseline")
            summary = (
                "The current HMM/GMM runtime-adjacent regime owner remains the best bounded "
                "shadow baseline on the present feature-table benchmark. Keep runtime unchanged "
                "and only revisit dependency widening after a deeper history window is tested."
            )
            next_test = (
                "Preserve the current runtime scorer, collect a longer benchmark window, and "
                "rerun `d5 run-shadow regime-model-compare-v1` before considering any "
                "statsmodels-based follow-on."
            )

        proposal_metrics = {
            "feature_bucket_rows": float(feature_rows),
            "massive_history_present": 1.0 if massive_present else 0.0,
            "massive_history_rows": float(history_inventory["massive_history"]["row_count"]),
            "recommended_is_statsmodels": 1.0 if best.key == "statsmodels" else 0.0,
            "statsmodels_available": 1.0 if candidate_results["statsmodels"].available else 0.0,
            "statsmodels_fit_success": 1.0 if candidate_results["statsmodels"].fit_success else 0.0,
            "best_adjacent_flip_rate": float(best.adjacent_flip_rate),
            "best_semantic_mapping_coverage": float(best.semantic_mapping_coverage),
        }
        return {
            "recommended_candidate": best.key,
            "summary": summary,
            "next_test": next_test,
            "reason_codes": reason_codes,
            "proposal_metrics": proposal_metrics,
        }

    def _build_history_inventory(
        self,
        feature_run_id: str,
        history: pd.DataFrame,
    ) -> dict[str, Any]:
        session = get_session(self.settings)
        try:
            grouped_rows = (
                session.query(
                    MarketCandle.venue,
                    MarketCandle.product_id,
                    MarketCandle.granularity,
                    func.count(MarketCandle.id),
                    func.min(MarketCandle.start_time_utc),
                    func.max(MarketCandle.start_time_utc),
                )
                .group_by(
                    MarketCandle.venue,
                    MarketCandle.product_id,
                    MarketCandle.granularity,
                )
                .order_by(
                    MarketCandle.venue.asc(),
                    MarketCandle.product_id.asc(),
                    MarketCandle.granularity.asc(),
                )
                .all()
            )
            market_inventory = [
                {
                    "venue": venue,
                    "product_id": product_id,
                    "granularity": granularity,
                    "row_count": int(row_count or 0),
                    "start_time_utc": ensure_utc(start_time).isoformat()
                    if ensure_utc(start_time) is not None
                    else "",
                    "end_time_utc": ensure_utc(end_time).isoformat()
                    if ensure_utc(end_time) is not None
                    else "",
                }
                for venue, product_id, granularity, row_count, start_time, end_time in grouped_rows
            ]
        finally:
            session.close()

        massive_rows = [row for row in market_inventory if row["venue"] == "massive"]
        return {
            "feature_history": {
                "feature_run_id": feature_run_id,
                "row_count": int(len(history)),
                "bucket_start_utc": history["bucket_start_utc"].iloc[0].isoformat()
                if not history.empty
                else "",
                "bucket_end_utc": history["bucket_start_utc"].iloc[-1].isoformat()
                if not history.empty
                else "",
                "massive_backed_rows": int(
                    history["proxy_products_json"]
                    .fillna("")
                    .astype(str)
                    .str.contains("X:")
                    .sum()
                )
                if "proxy_products_json" in history.columns
                else 0,
            },
            "market_candle_inventory": market_inventory,
            "massive_history": {
                "present": bool(massive_rows),
                "row_count": int(sum(row["row_count"] for row in massive_rows)),
                "products": sorted({row["product_id"] for row in massive_rows}),
            },
        }

    def _comparison_payload(
        self,
        *,
        run_id: str,
        config_payload: dict[str, Any],
        history_inventory: dict[str, Any],
        candidate_results: dict[str, _CandidateOutcome],
        recommendation_payload: dict[str, Any] | None,
        status: str,
        error_message: str | None,
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "experiment_name": _COMPARE_RUN_NAME,
            "status": status,
            "error_message": error_message,
            "config": config_payload,
            "history_inventory": history_inventory,
            "candidates": {
                key: {
                    "model_family": result.model_family,
                    "available": result.available,
                    "fit_success": result.fit_success,
                    "fit_seconds": result.fit_seconds,
                    "prediction_rows": result.prediction_rows,
                    "state_count": result.state_count,
                    "mean_confidence": result.mean_confidence,
                    "adjacent_flip_rate": result.adjacent_flip_rate,
                    "semantic_mapping_coverage": result.semantic_mapping_coverage,
                    "semantic_shares": result.semantic_shares,
                    "fail_closed": result.fail_closed,
                    "log_likelihood": result.log_likelihood,
                    "error": result.error,
                    "history_preview": result.scored_history[-20:],
                }
                for key, result in candidate_results.items()
            },
            "recommendation": recommendation_payload,
            "generated_at": utcnow().isoformat(),
        }

    def _write_artifacts(
        self,
        *,
        run_id: str,
        artifact_dir: Path,
        config_payload: dict[str, Any],
        history_inventory: dict[str, Any],
        comparison_payload: dict[str, Any],
    ) -> None:
        write_json_artifact(
            artifact_dir / "config.json",
            config_payload,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="regime_model_compare_config",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "history_inventory.json",
            history_inventory,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="regime_model_compare_history_inventory",
            settings=self.settings,
        )
        write_json_artifact(
            artifact_dir / "comparison.json",
            comparison_payload,
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="regime_model_compare_summary",
            settings=self.settings,
        )
        write_text_artifact(
            artifact_dir / "report.qmd",
            self._render_report_qmd(
                config_payload=config_payload,
                comparison_payload=comparison_payload,
            ),
            owner_type="experiment_run",
            owner_key=run_id,
            artifact_type="regime_model_compare_report_qmd",
            artifact_format="qmd",
            settings=self.settings,
        )

    def _render_report_qmd(
        self,
        *,
        config_payload: dict[str, Any],
        comparison_payload: dict[str, Any],
    ) -> str:
        history_inventory = comparison_payload["history_inventory"]
        run_id = str(comparison_payload["run_id"])
        candidate_lines: list[str] = []
        for key in _CANDIDATE_ORDER:
            candidate = comparison_payload["candidates"].get(key)
            if not candidate:
                candidate_lines.append(f"- `{key}`: no candidate payload")
                continue
            candidate_lines.append(
                f"- `{key}` family=`{candidate['model_family']}` available=`{candidate['available']}` "
                f"fit_success=`{candidate['fit_success']}` rows=`{candidate['prediction_rows']}` "
                f"flip_rate=`{candidate['adjacent_flip_rate']}` mean_conf=`{candidate['mean_confidence']}`"
            )
            if candidate.get("error"):
                candidate_lines.append(f"- `{key}` error: `{candidate['error']}`")

        recommendation = comparison_payload.get("recommendation") or {}
        recommendation_lines = (
            [
                f"- recommended candidate: `{recommendation.get('recommended_candidate', 'none')}`",
                recommendation.get("summary", "- no recommendation summary"),
                recommendation.get("next_test", "- no next test recorded"),
            ]
            if recommendation
            else ["- no recommendation recorded"]
        )
        return render_qmd(
            "experiment_run.qmd",
            title=_COMPARE_RUN_NAME,
            metadata=trading_report_metadata(
                report_kind="regime_model_compare",
                run_id=run_id,
                owner_type="experiment_run",
                owner_key=run_id,
                instrument_scope=["SOL/USDC"],
                context_instruments=["BTC/USD", "ETH/USD"],
                timeframe="15m",
                summary_path="comparison.json",
                config_path="config.json",
            ),
            summary_lines=[
                f"- feature run: `{config_payload['feature_run_id']}`",
                f"- feature buckets: `{config_payload['feature_bucket_rows']}`",
                f"- train window buckets: `{config_payload['train_window_buckets']}`",
                f"- refit cadence: `{config_payload['refit_cadence_buckets']}`",
                f"- macro context: `{config_payload['macro_context_state']}`",
                f"- Massive history present: `{history_inventory['massive_history']['present']}`",
                f"- status: `{comparison_payload['status']}`",
            ],
            sections=[
                ("Market / Source Context", [
                    f"- row count: `{history_inventory['feature_history']['row_count']}`",
                    f"- bucket start: `{history_inventory['feature_history']['bucket_start_utc']}`",
                    f"- bucket end: `{history_inventory['feature_history']['bucket_end_utc']}`",
                    f"- Massive history rows: `{history_inventory['massive_history']['row_count']}`",
                ]),
                ("Regime / Condition / Policy / Risk", candidate_lines or ["- no candidates recorded"]),
                ("Bounded Next Change", recommendation_lines),
                ("Failure Attribution", [f"- `{comparison_payload['error_message']}`"] if comparison_payload.get("error_message") else ["- weakest surface: `inconclusive / sample too small`"]),
            ],
        )

    def _record_metrics(
        self,
        *,
        run_id: str,
        history: pd.DataFrame,
        history_inventory: dict[str, Any],
        candidate_results: dict[str, _CandidateOutcome],
    ) -> None:
        session = get_session(self.settings)
        now = utcnow()
        try:
            rows = [
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="dataset_rows",
                    metric_value=float(len(history)),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="feature_bucket_rows",
                    metric_value=float(history_inventory["feature_history"]["row_count"]),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="train_window_buckets",
                    metric_value=float(_TRAIN_WINDOW_BUCKETS),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="evaluation_buckets",
                    metric_value=float(max(len(history) - (_TRAIN_WINDOW_BUCKETS - 1), 0)),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="massive_history_present",
                    metric_value=(
                        1.0 if history_inventory["massive_history"]["present"] else 0.0
                    ),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="massive_history_rows",
                    metric_value=float(history_inventory["massive_history"]["row_count"]),
                    metric_metadata=None,
                    recorded_at=now,
                ),
                ExperimentMetric(
                    experiment_run_id=run_id,
                    metric_name="massive_backed_feature_rows",
                    metric_value=float(history_inventory["feature_history"]["massive_backed_rows"]),
                    metric_metadata=None,
                    recorded_at=now,
                ),
            ]
            for key in _CANDIDATE_ORDER:
                result = candidate_results.get(key)
                if result is None:
                    continue
                for metric_name, metric_value in result.metric_payload().items():
                    rows.append(
                        ExperimentMetric(
                            experiment_run_id=run_id,
                            metric_name=f"{key}_{metric_name}",
                            metric_value=float(metric_value),
                            metric_metadata=result.error if metric_name == "fail_closed" else None,
                            recorded_at=now,
                        )
                    )
            session.add_all(rows)
            session.commit()
        finally:
            session.close()

    def _filter_history(
        self,
        history: pd.DataFrame,
        *,
        history_start: str | None,
        history_end: str | None,
        use_massive_context: bool,
    ) -> pd.DataFrame:
        filtered = history.copy()
        if history_start:
            start_ts = pd.Timestamp(history_start, tz="UTC")
            filtered = filtered.loc[filtered["bucket_start_utc"] >= start_ts]
        if history_end:
            end_ts = pd.Timestamp(history_end, tz="UTC")
            filtered = filtered.loc[filtered["bucket_start_utc"] <= end_ts]
        if not use_massive_context and "proxy_products_json" in filtered.columns:
            filtered = filtered.loc[
                ~filtered["proxy_products_json"].fillna("").astype(str).str.contains("X:")
            ]
        return filtered.reset_index(drop=True)

    def _start_experiment_run(
        self,
        run_id: str,
        *,
        experiment_name: str,
        hypothesis: str,
        config_payload: dict[str, Any],
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
