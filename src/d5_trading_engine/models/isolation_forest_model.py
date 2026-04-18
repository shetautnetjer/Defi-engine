"""Isolation Forest anomaly adapter for bounded research workflows."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest as SklearnIsolationForest

from d5_trading_engine.models.base import BaseModel


class IsolationForestModel(BaseModel):
    """Isolation Forest wrapper for anomaly scoring and flags."""

    family = "isolation_forest"

    DEFAULT_PARAMS: dict[str, Any] = {
        "n_estimators": 200,
        "contamination": "auto",
        "max_features": 1.0,
        "max_samples": "auto",
        "random_state": 42,
        "n_jobs": -1,
    }

    def __init__(
        self,
        model_version: str = "0.1.0",
        contamination: float | str = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(model_version=model_version, **kwargs)
        params = dict(self.DEFAULT_PARAMS)
        params["contamination"] = contamination
        params.update(kwargs)
        self._contamination = contamination
        self._model = SklearnIsolationForest(**params)

    def train(self, X: pd.DataFrame, y: pd.Series | None = None, **kwargs: Any) -> dict:
        del y, kwargs
        self._model.fit(X)
        scores = self._model.score_samples(X)
        labels = self._model.predict(X)
        anomaly_count = int(np.sum(labels == -1))
        return {
            "n_samples": X.shape[0],
            "n_features": X.shape[1],
            "anomaly_count": anomaly_count,
            "anomaly_rate": anomaly_count / X.shape[0] if X.shape[0] else 0.0,
            "mean_anomaly_score": float(np.mean(scores)),
            "std_anomaly_score": float(np.std(scores)),
        }

    def predict(self, X: pd.DataFrame, **kwargs: Any) -> np.ndarray:
        return np.asarray(self._model.predict(X, **kwargs))

    def score_samples(self, X: pd.DataFrame) -> np.ndarray:
        return np.asarray(self._model.score_samples(X))

    def anomaly_flags(
        self,
        X: pd.DataFrame,
        threshold: float | None = None,
    ) -> pd.DataFrame:
        scores = self.score_samples(X)
        labels = self.predict(X)
        result = pd.DataFrame(
            {
                "anomaly_score": scores,
                "anomaly_label": labels,
                "is_anomaly": labels == -1,
            },
            index=X.index,
        )
        if threshold is not None:
            result["is_anomaly_custom"] = scores < threshold
        return result

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        del y, kwargs
        scores = self.score_samples(X)
        labels = self.predict(X)
        anomaly_count = int(np.sum(labels == -1))
        return {
            "anomaly_rate": anomaly_count / len(X) if len(X) else 0.0,
            "mean_score": float(np.mean(scores)),
            "min_score": float(np.min(scores)),
            "max_score": float(np.max(scores)),
            "std_score": float(np.std(scores)),
        }

    @staticmethod
    def tune_contamination(
        X: pd.DataFrame,
        candidates: list[float] | None = None,
    ) -> dict[str, Any]:
        if candidates is None:
            candidates = [0.01, 0.02, 0.05, 0.10, 0.15]

        results = []
        for contamination in candidates:
            model = SklearnIsolationForest(
                contamination=contamination,
                n_estimators=100,
                random_state=42,
            )
            model.fit(X)
            scores = model.score_samples(X)
            labels = model.predict(X)
            anomaly_count = int(np.sum(labels == -1))
            results.append(
                {
                    "contamination": contamination,
                    "anomaly_count": anomaly_count,
                    "anomaly_rate": anomaly_count / len(X) if len(X) else 0.0,
                    "mean_score": float(np.mean(scores)),
                    "threshold_score": float(np.percentile(scores, contamination * 100)),
                }
            )
        return {"candidates": results}

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        with (path / "model.pkl").open("wb") as handle:
            pickle.dump(self._model, handle)
        (path / "meta.json").write_text(
            json.dumps(
                {
                    "family": self.family,
                    "version": self.model_version,
                    "contamination": str(self._contamination),
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def load(self, path: Path) -> None:
        with (path / "model.pkl").open("rb") as handle:
            self._model = pickle.load(handle)  # noqa: S301
