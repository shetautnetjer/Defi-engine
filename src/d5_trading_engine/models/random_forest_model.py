"""CPU-safe Random Forest adapter for D5 research workflows."""

from __future__ import annotations

import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from d5_trading_engine.models.base import BaseModel


class RandomForestModel(BaseModel):
    """Random Forest wrapper with deterministic defaults."""

    family = "random_forest"

    DEFAULT_PARAMS: dict[str, Any] = {
        "n_estimators": 200,
        "max_depth": 12,
        "min_samples_split": 5,
        "min_samples_leaf": 2,
        "max_features": "sqrt",
        "random_state": 42,
        "n_jobs": -1,
    }

    def __init__(
        self,
        model_version: str = "0.1.0",
        task: str = "classification",
        **kwargs: Any,
    ) -> None:
        super().__init__(model_version=model_version, **kwargs)
        self.task = task
        params = dict(self.DEFAULT_PARAMS)
        params.update(kwargs)
        if task == "regression":
            self._model = RandomForestRegressor(**params)
        else:
            self._model = RandomForestClassifier(oob_score=True, **params)
        self._train_metrics: dict[str, Any] = {}

    def train(self, X: pd.DataFrame, y: pd.Series | None = None, **kwargs: Any) -> dict:
        if y is None:
            raise ValueError("RandomForestModel.train requires a target series.")
        self._model.fit(X, y, **kwargs)
        self._train_metrics = {
            "n_features": X.shape[1],
            "n_samples": X.shape[0],
            "task": self.task,
        }
        oob_score = getattr(self._model, "oob_score_", None)
        if oob_score is not None:
            self._train_metrics["oob_score"] = float(oob_score)
        return dict(self._train_metrics)

    def predict(self, X: pd.DataFrame, **kwargs: Any) -> np.ndarray:
        return np.asarray(self._model.predict(X, **kwargs))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.task != "classification":
            raise ValueError("predict_proba is only available for classification tasks.")
        return np.asarray(self._model.predict_proba(X))

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        with (path / "model.pkl").open("wb") as handle:
            pickle.dump(self._model, handle)
        (path / "meta.json").write_text(
            json.dumps(
                {
                    "family": self.family,
                    "version": self.model_version,
                    "task": self.task,
                    "train_metrics": self._train_metrics,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def load(self, path: Path) -> None:
        with (path / "model.pkl").open("rb") as handle:
            self._model = pickle.load(handle)  # noqa: S301

    def feature_importance(self) -> dict[str, float] | None:
        importances = getattr(self._model, "feature_importances_", None)
        if importances is None:
            return None
        names = getattr(self._model, "feature_names_in_", None)
        if names is None:
            names = [f"f{i}" for i in range(len(importances))]
        return dict(zip(names, np.asarray(importances).tolist(), strict=False))
