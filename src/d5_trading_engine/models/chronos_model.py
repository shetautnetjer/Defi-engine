"""Optional Chronos-2 forecasting adapter for shadow-only research."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from d5_trading_engine.models.base import BaseModel

log = logging.getLogger(__name__)

_CHRONOS_AVAILABLE = False
try:
    from chronos import Chronos2Pipeline  # type: ignore[import-untyped]

    _CHRONOS_AVAILABLE = True
except ImportError:
    Chronos2Pipeline = None  # type: ignore[assignment]


def chronos_available() -> bool:
    """Return True when Chronos-2 optional dependencies are installed."""
    return _CHRONOS_AVAILABLE


class ChronosModel(BaseModel):
    """Pre-trained Chronos-2 forecast adapter."""

    family = "chronos_2"
    DEFAULT_QUANTILES = [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95]

    def __init__(
        self,
        model_version: str = "0.1.0",
        model_id: str = "amazon/chronos-2",
        device: str | None = None,
        prediction_length: int = 12,
        quantile_levels: list[float] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(model_version=model_version, **kwargs)
        self.model_id = model_id
        self.prediction_length = prediction_length
        self.quantile_levels = quantile_levels or list(self.DEFAULT_QUANTILES)
        self._device = device or "cpu"
        self._pipeline = None

        if not _CHRONOS_AVAILABLE:
            self._device = "unavailable"
            return

        if device is None:
            try:
                import torch

                self._device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self._device = "cpu"

        self._pipeline = Chronos2Pipeline.from_pretrained(
            self.model_id,
            device_map=self._device,
        )

    def train(self, X: pd.DataFrame, y: pd.Series | None = None, **kwargs: Any) -> dict:
        del X, y, kwargs
        return {
            "status": "pretrained",
            "model_id": self.model_id,
            "device": self._device,
            "available": _CHRONOS_AVAILABLE,
            "prediction_length": self.prediction_length,
        }

    def predict(self, X: pd.DataFrame, **kwargs: Any) -> np.ndarray:
        forecast = self.forecast(X, **kwargs)
        if forecast is None or "0.5" not in forecast.columns:
            return np.full(self.prediction_length, np.nan)
        return forecast["0.5"].to_numpy()

    def forecast(
        self,
        context_df: pd.DataFrame,
        future_df: pd.DataFrame | None = None,
        target_col: str = "price_usdc",
        timestamp_col: str | None = "ts_event",
        **kwargs: Any,
    ) -> pd.DataFrame | None:
        if self._pipeline is None:
            log.warning("ChronosModel.forecast called without optional Chronos dependencies.")
            return None
        try:
            return self._pipeline.predict_df(
                context_df,
                future_df=future_df,
                prediction_length=self.prediction_length,
                quantile_levels=self.quantile_levels,
                timestamp_column=timestamp_col,
                target=target_col,
                **kwargs,
            )
        except Exception as exc:
            log.warning("Chronos forecast failed: %s", exc)
            return None

    def forecast_simple(self, prices: list[float] | np.ndarray) -> dict[str, list[float]] | None:
        frame = pd.DataFrame({"price_usdc": prices})
        forecast = self.forecast(frame, target_col="price_usdc", timestamp_col=None)
        if forecast is None:
            return None
        return {
            str(level): forecast[str(level)].tolist()
            for level in self.quantile_levels
            if str(level) in forecast.columns
        }

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        (path / "meta.json").write_text(
            json.dumps(
                {
                    "family": self.family,
                    "version": self.model_version,
                    "model_id": self.model_id,
                    "device": self._device,
                    "prediction_length": self.prediction_length,
                    "quantile_levels": self.quantile_levels,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def load(self, path: Path) -> None:
        meta_path = path / "meta.json"
        if not meta_path.exists():
            return
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        self.model_id = metadata.get("model_id", self.model_id)
        self.prediction_length = metadata.get(
            "prediction_length",
            self.prediction_length,
        )
        self.quantile_levels = metadata.get("quantile_levels", self.quantile_levels)

    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series | None = None,
        **kwargs: Any,
    ) -> dict[str, float]:
        predictions = self.predict(X, **kwargs)
        if y is None or np.all(np.isnan(predictions)):
            return {"status": -1.0}

        n = min(len(predictions), len(y))
        actual = y.to_numpy()[:n]
        predictions = predictions[:n]
        return {
            "mse": float(np.mean((predictions - actual) ** 2)),
            "mae": float(np.mean(np.abs(predictions - actual))),
            "mape": float(
                np.mean(
                    np.abs((predictions - actual) / np.where(actual == 0, 1, actual))
                )
            ),
        }
