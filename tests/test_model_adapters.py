from __future__ import annotations

import numpy as np
import pandas as pd

from d5_trading_engine.models import (
    ChronosModel,
    IsolationForestModel,
    RandomForestModel,
    XGBoostModel,
    chronos_available,
)


def _classification_frame() -> tuple[pd.DataFrame, pd.Series]:
    X = pd.DataFrame(
        {
            "f0": [0.0, 1.0, 0.1, 0.9, 0.2, 0.8, 0.3, 0.7],
            "f1": [1.0, 0.0, 0.9, 0.1, 0.8, 0.2, 0.7, 0.3],
        }
    )
    y = pd.Series([0, 1, 0, 1, 0, 1, 0, 1])
    return X, y


def test_random_forest_model_train_predict_save_load(tmp_path) -> None:
    X, y = _classification_frame()
    model = RandomForestModel()

    metrics = model.train(X, y)
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    evaluation = model.evaluate(X, y)
    artifact_path = model.get_artifact_path(tmp_path)
    model.save(artifact_path)

    reloaded = RandomForestModel()
    reloaded.load(artifact_path)
    reloaded_predictions = reloaded.predict(X)

    assert metrics["n_samples"] == len(X)
    assert probabilities.shape == (len(X), 2)
    assert evaluation["accuracy"] >= 0.5
    assert len(predictions) == len(X)
    assert np.array_equal(predictions, reloaded_predictions)
    assert model.feature_importance() is not None


def test_xgboost_model_train_predict_save_load(tmp_path) -> None:
    X, y = _classification_frame()
    model = XGBoostModel(n_estimators=20, max_depth=2)

    metrics = model.train(X, y)
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)
    evaluation = model.evaluate(X, y)
    artifact_path = model.get_artifact_path(tmp_path)
    model.save(artifact_path)

    reloaded = XGBoostModel(n_estimators=20, max_depth=2)
    reloaded.load(artifact_path)
    reloaded_predictions = reloaded.predict(X)

    assert metrics["n_samples"] == len(X)
    assert probabilities.shape == (len(X), 2)
    assert evaluation["accuracy"] >= 0.5
    assert len(predictions) == len(X)
    assert len(reloaded_predictions) == len(X)
    assert model.feature_importance() is not None


def test_isolation_forest_model_supports_scores_flags_and_save_load(tmp_path) -> None:
    X, _ = _classification_frame()
    model = IsolationForestModel(contamination=0.25, n_estimators=50)

    metrics = model.train(X)
    predictions = model.predict(X)
    scores = model.score_samples(X)
    flags = model.anomaly_flags(X)
    evaluation = model.evaluate(X)
    tuned = model.tune_contamination(X, candidates=[0.1, 0.2])
    artifact_path = model.get_artifact_path(tmp_path)
    model.save(artifact_path)

    reloaded = IsolationForestModel(contamination=0.25, n_estimators=50)
    reloaded.load(artifact_path)
    reloaded_predictions = reloaded.predict(X)

    assert metrics["n_samples"] == len(X)
    assert len(predictions) == len(X)
    assert len(scores) == len(X)
    assert list(flags.columns)[:3] == ["anomaly_score", "anomaly_label", "is_anomaly"]
    assert "anomaly_rate" in evaluation
    assert len(tuned["candidates"]) == 2
    assert len(reloaded_predictions) == len(X)


def test_chronos_model_gracefully_handles_unavailable_optional_dependency(tmp_path) -> None:
    if chronos_available():
        # The optional Chronos surface is exercised as an availability contract only here.
        assert chronos_available() is True
        return

    model = ChronosModel(prediction_length=4)
    frame = pd.DataFrame({"price_usdc": [100.0, 101.0, 102.0, 103.0]})
    artifact_path = model.get_artifact_path(tmp_path)
    model.save(artifact_path)

    metadata_model = ChronosModel(prediction_length=4)
    metadata_model.load(artifact_path)
    predictions = model.predict(frame)
    evaluation = model.evaluate(frame)

    assert metadata_model.prediction_length == 4
    assert len(predictions) == 4
    assert np.all(np.isnan(predictions))
    assert evaluation["status"] == -1.0
