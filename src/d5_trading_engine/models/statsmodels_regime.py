"""Optional statsmodels-based shadow regime candidate."""

from __future__ import annotations

from typing import Any

import numpy as np

_STATSMODELS_AVAILABLE = False
try:
    from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression

    _STATSMODELS_AVAILABLE = True
except ModuleNotFoundError:
    MarkovRegression = None  # type: ignore[assignment]


def statsmodels_regime_available() -> bool:
    """Return True when the optional statsmodels dependency is installed."""
    return _STATSMODELS_AVAILABLE


def fit_markov_regression(
    endog,
    *,
    k_regimes: int,
    trend: str = "c",
    switching_variance: bool = True,
    fit_kwargs: dict[str, Any] | None = None,
) -> tuple[object, str]:
    """Fit a bounded Markov-switching regression over one endogenous series."""
    if not _STATSMODELS_AVAILABLE:
        raise ModuleNotFoundError("statsmodels is not installed")

    fit_kwargs = fit_kwargs or {"disp": False}
    model = MarkovRegression(
        np.asarray(endog, dtype=float),
        k_regimes=k_regimes,
        trend=trend,
        switching_variance=switching_variance,
    )
    result = model.fit(**fit_kwargs)
    return result, f"statsmodels_markov_regression_{k_regimes}state"


def filter_markov_regression(
    *,
    params,
    endog,
    k_regimes: int,
    trend: str = "c",
    switching_variance: bool = True,
):
    """Apply fitted parameters to a new bounded time series without re-estimating."""
    if not _STATSMODELS_AVAILABLE:
        raise ModuleNotFoundError("statsmodels is not installed")

    model = MarkovRegression(
        np.asarray(endog, dtype=float),
        k_regimes=k_regimes,
        trend=trend,
        switching_variance=switching_variance,
    )
    return model.filter(params)


def predict_markov_regime_states(result: object) -> tuple[np.ndarray, np.ndarray]:
    """Return latent state ids and probabilities from a statsmodels result."""
    probabilities = getattr(result, "filtered_marginal_probabilities", None)
    if probabilities is None:
        probabilities = getattr(result, "smoothed_marginal_probabilities", None)
    if probabilities is None:
        raise RuntimeError("statsmodels result did not expose marginal probabilities")

    matrix = _probability_matrix(probabilities)
    return matrix.argmax(axis=1), matrix


def markov_log_likelihood(result: object) -> float | None:
    """Return the fitted log likelihood when available."""
    value = getattr(result, "llf", None)
    return None if value is None else float(value)


def _probability_matrix(probabilities) -> np.ndarray:
    matrix = np.asarray(probabilities, dtype=float)
    if matrix.ndim != 2:
        raise RuntimeError("statsmodels marginal probabilities must be two-dimensional")
    if matrix.shape[0] <= 8 and matrix.shape[1] > matrix.shape[0]:
        matrix = matrix.T
    return matrix
