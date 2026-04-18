"""Model ownership surfaces for runtime-adjacent and shadow-only research lanes."""

from d5_trading_engine.models.base import BaseModel
from d5_trading_engine.models.chronos_model import ChronosModel, chronos_available
from d5_trading_engine.models.ensemble_baselines import (
    RUNTIME_ADJACENT_MODELS,
    build_isolation_forest,
    build_random_forest_classifier,
    build_xgboost_classifier,
)
from d5_trading_engine.models.isolation_forest_model import IsolationForestModel
from d5_trading_engine.models.random_forest_model import RandomForestModel
from d5_trading_engine.models.shadow_only import SHADOW_ONLY_MODELS
from d5_trading_engine.models.statsmodels_regime import (
    fit_markov_regression,
    markov_log_likelihood,
    predict_markov_regime_states as predict_statsmodels_regime_states,
    statsmodels_regime_available,
)
from d5_trading_engine.models.xgboost_model import XGBoostModel

__all__ = [
    "BaseModel",
    "ChronosModel",
    "IsolationForestModel",
    "RandomForestModel",
    "RUNTIME_ADJACENT_MODELS",
    "SHADOW_ONLY_MODELS",
    "XGBoostModel",
    "build_isolation_forest",
    "build_random_forest_classifier",
    "build_xgboost_classifier",
    "chronos_available",
    "fit_markov_regression",
    "markov_log_likelihood",
    "predict_statsmodels_regime_states",
    "statsmodels_regime_available",
]
