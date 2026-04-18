"""Reusable base interface for D5 model adapters."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class BaseModel(ABC):
    """Uniform adapter contract for reusable research models."""

    family: str = ""

    def __init__(self, model_version: str = "0.1.0", **kwargs: Any) -> None:
        self.model_version = model_version
        self._model: Any = None
        self._params = dict(kwargs)

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series | None = None, **kwargs: Any) -> dict:
        """Train or initialize the model and return metadata."""

    @abstractmethod
    def predict(self, X: pd.DataFrame, **kwargs: Any) -> np.ndarray:
        """Generate model predictions."""

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        """Return default classification/regression metrics when ground truth exists."""
        predictions = np.asarray(self.predict(X, **kwargs))
        if y is None:
            return {"status": -1.0}

        actual = np.asarray(y)
        metrics: dict[str, float] = {}
        if predictions.size == 0 or actual.size == 0:
            return {"status": -1.0}

        if np.issubdtype(predictions.dtype, np.integer) or set(np.unique(predictions)).issubset(
            {0, 1, -1}
        ):
            metrics["accuracy"] = float(np.mean(predictions == actual))

        metrics["mse"] = float(np.mean((predictions - actual) ** 2))
        metrics["mae"] = float(np.mean(np.abs(predictions - actual)))
        return metrics

    @abstractmethod
    def save(self, path: Path) -> None:
        """Persist model artifacts to disk."""

    @abstractmethod
    def load(self, path: Path) -> None:
        """Load model artifacts from disk."""

    def get_artifact_path(self, base_dir: Path) -> Path:
        """Return the standard artifact directory for this model family/version."""
        path = base_dir / self.family / self.model_version
        path.mkdir(parents=True, exist_ok=True)
        return path

    def feature_importance(self) -> dict[str, float] | None:
        """Return feature-importance scores when the backend exposes them."""
        return None

    @staticmethod
    def gpu_available() -> bool:
        """Return True when CUDA tooling appears to be available."""
        try:
            result = subprocess.run(
                ["nvidia-smi"],
                check=False,
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(family={self.family!r}, version={self.model_version!r})"
