from __future__ import annotations

import pandas as pd

from d5_trading_engine.paper_runtime.training_profiles import (
    assess_training_history_window,
    get_training_profile,
    summarize_training_profile_readiness,
)


def test_summarize_training_profile_readiness_marks_quickstart_ready_before_full() -> None:
    summary = summarize_training_profile_readiness(
        available_history_days=335,
        selected_profile_name="full_730d",
    )

    assert summary["selected_profile_name"] == "full_730d"
    assert summary["profiles"]["quickstart_300d"]["ready"] is True
    assert summary["profiles"]["quickstart_300d"]["shortfall_days"] == 0
    assert summary["profiles"]["full_730d"]["ready"] is False
    assert summary["profiles"]["full_730d"]["shortfall_days"] == 120


def test_get_training_profile_auto_selects_strongest_ready_profile() -> None:
    selected = get_training_profile("auto", available_history_days=335)

    assert selected.name == "quickstart_300d"
    assert selected.confidence_label == "quickstart"


def test_assess_training_history_window_requires_profile_thresholds() -> None:
    quickstart = get_training_profile("quickstart_300d")
    full = get_training_profile("full_730d")
    history_start = pd.Timestamp("2025-01-01T00:00:00Z")
    history_end = pd.Timestamp("2025-11-30T00:00:00Z")

    quickstart_readiness = assess_training_history_window(
        history_start=history_start,
        history_end=history_end,
        profile=quickstart,
    )
    full_readiness = assess_training_history_window(
        history_start=history_start,
        history_end=history_end,
        profile=full,
    )

    assert quickstart_readiness["ready"] is True
    assert quickstart_readiness["available_history_days"] >= 300
    assert full_readiness["ready"] is False
    assert full_readiness["required_history_days"] == 455
