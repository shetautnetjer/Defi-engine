"""Runtime-adjacent regime-model ownership for bounded condition scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.mixture import GaussianMixture


def hmmlearn_available() -> bool:
    """Return True when the optional hmmlearn dependency is installed."""
    try:
        from hmmlearn.hmm import GaussianHMM
    except ModuleNotFoundError:
        return False
    return GaussianHMM is not None


def fit_gaussian_hmm(feature_matrix, *, n_components: int) -> tuple[object, str]:
    """Fit the bounded Gaussian HMM regime owner."""
    from hmmlearn.hmm import GaussianHMM

    model = GaussianHMM(
        n_components=n_components,
        covariance_type="diag",
        n_iter=200,
        random_state=42,
    )
    model.fit(feature_matrix)
    return model, f"gaussian_hmm_{n_components}state"


def fit_gaussian_mixture_regime_proxy(feature_matrix, *, n_components: int) -> tuple[object, str]:
    """Fit the bounded Gaussian-mixture proxy used when hmmlearn is absent."""
    model = GaussianMixture(
        n_components=n_components,
        covariance_type="diag",
        n_init=5,
        random_state=42,
    )
    model.fit(feature_matrix)
    return model, f"gaussian_mixture_regime_proxy_{n_components}state"


def fit_hmm_or_gmm(feature_matrix, *, n_components: int) -> tuple[object, str]:
    """Fit the preferred regime model, falling back to GMM when hmmlearn is absent."""
    if not hmmlearn_available():
        return fit_gaussian_mixture_regime_proxy(feature_matrix, n_components=n_components)
    return fit_gaussian_hmm(feature_matrix, n_components=n_components)


def predict_regime_states(model: object, feature_matrix) -> tuple[np.ndarray, np.ndarray]:
    """Predict latent regime states and per-row probabilities."""
    return np.asarray(model.predict(feature_matrix)), np.asarray(model.predict_proba(feature_matrix))


def map_regime_state_semantics(history: pd.DataFrame) -> dict[int, dict[str, object]]:
    """Map latent states onto the shared bounded semantic regime labels."""
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
