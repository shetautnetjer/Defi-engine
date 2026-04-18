"""XGBoost adapter with deterministic CPU-safe defaults."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import xgboost as xgb

from d5_trading_engine.models.base import BaseModel


class XGBoostModel(BaseModel):
    """XGBoost wrapper for bounded research evaluation."""

    family = "xgboost"

    DEFAULT_PARAMS: dict[str, Any] = {
        "n_estimators": 200,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 3,
        "gamma": 0.1,
        "reg_alpha": 0.1,
        "reg_lambda": 1.0,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "random_state": 42,
        "tree_method": "hist",
        "device": "cpu",
    }

    def __init__(
        self,
        model_version: str = "0.1.0",
        task: str = "classification",
        use_gpu: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_version=model_version, **kwargs)
        self.task = task
        self._use_gpu = bool(use_gpu and self.gpu_available())
        params = dict(self.DEFAULT_PARAMS)
        params.update(kwargs)
        params["device"] = "cuda" if self._use_gpu else "cpu"

        if task == "regression":
            params["objective"] = "reg:squarederror"
            params["eval_metric"] = "rmse"
            self._model = xgb.XGBRegressor(**params)
        else:
            self._model = xgb.XGBClassifier(**params)
        self._train_metrics: dict[str, Any] = {}

    def train(self, X: pd.DataFrame, y: pd.Series | None = None, **kwargs: Any) -> dict:
        if y is None:
            raise ValueError("XGBoostModel.train requires a target series.")
        self._model.fit(X, y, **kwargs)
        self._train_metrics = {
            "n_features": X.shape[1],
            "n_samples": X.shape[0],
            "gpu_used": self._use_gpu,
            "task": self.task,
        }
        return dict(self._train_metrics)

    def predict(self, X: pd.DataFrame, **kwargs: Any) -> np.ndarray:
        return np.asarray(self._model.predict(X, **kwargs))

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.task != "classification":
            raise ValueError("predict_proba is only available for classification tasks.")
        return np.asarray(self._model.predict_proba(X))

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self._model.save_model(str(path / "model.json"))
        (path / "meta.json").write_text(
            json.dumps(
                {
                    "family": self.family,
                    "version": self.model_version,
                    "task": self.task,
                    "gpu_trained": self._use_gpu,
                    "params": self._model.get_params(),
                },
                indent=2,
                sort_keys=True,
                default=str,
            ),
            encoding="utf-8",
        )

    def load(self, path: Path) -> None:
        self._model.load_model(str(path / "model.json"))

    def feature_importance(self) -> dict[str, float] | None:
        importances = getattr(self._model, "feature_importances_", None)
        names = getattr(self._model, "feature_names_in_", None)
        if importances is None or names is None:
            return None
        return dict(zip(names, np.asarray(importances).tolist(), strict=False))

    @staticmethod
    def get_param_grid() -> dict[str, list]:
        return {
            "n_estimators": [100, 200, 500],
            "max_depth": [4, 6, 8, 10],
            "learning_rate": [0.01, 0.05, 0.1],
            "subsample": [0.7, 0.8, 0.9],
            "colsample_bytree": [0.7, 0.8, 0.9],
            "min_child_weight": [1, 3, 5],
        }
