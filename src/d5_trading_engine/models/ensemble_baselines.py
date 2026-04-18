"""Runtime-adjacent deterministic model builders for paper-first research."""

from __future__ import annotations

from sklearn.ensemble import IsolationForest, RandomForestClassifier
from xgboost import XGBClassifier


def build_isolation_forest(*, contamination: float = 0.08) -> IsolationForest:
    """Construct the bounded anomaly-veto model used by research lanes."""
    return IsolationForest(
        contamination=contamination,
        n_estimators=100,
        random_state=42,
    )


def build_random_forest_classifier() -> RandomForestClassifier:
    """Construct the deterministic Random Forest baseline."""
    return RandomForestClassifier(
        n_estimators=120,
        min_samples_leaf=2,
        random_state=42,
    )


def build_xgboost_classifier() -> XGBClassifier:
    """Construct the deterministic XGBoost baseline."""
    return XGBClassifier(
        n_estimators=80,
        max_depth=3,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        tree_method="hist",
        eval_metric="logloss",
        random_state=42,
    )


RUNTIME_ADJACENT_MODELS = {
    "deterministic_baselines": {
        "status": "runtime_adjacent",
        "notes": "Thresholded feature baselines remain operator-reviewable only.",
    },
    "random_forest": {
        "status": "runtime_adjacent",
        "notes": "Used for bounded experiment comparison only.",
    },
    "xgboost": {
        "status": "runtime_adjacent",
        "notes": "Used for bounded experiment comparison only.",
    },
    "isolation_forest": {
        "status": "runtime_adjacent",
        "notes": "Advisory anomaly veto only; no live authority.",
    },
    "hmm_condition_owner": {
        "status": "runtime_adjacent",
        "notes": "Condition ownership stays bounded to regime scoring.",
    },
}
