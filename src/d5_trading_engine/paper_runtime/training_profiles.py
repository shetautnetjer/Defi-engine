"""Paper-practice training regimens.

These profiles govern data budget, warmup, and replay shape only.
They do not hard-wire strategy, policy, or risk behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PaperPracticeTrainingProfile:
    name: str
    history_lookback_days: int
    minimum_training_days: int
    minimum_replay_days: int
    walk_forward_window_days: int
    confidence_label: str
    historical_sources: tuple[str, ...]
    context_sources: tuple[str, ...]

    @property
    def required_history_days(self) -> int:
        return self.minimum_training_days + self.minimum_replay_days


_PROFILE_CATALOG: dict[str, PaperPracticeTrainingProfile] = {
    "quickstart_300d": PaperPracticeTrainingProfile(
        name="quickstart_300d",
        history_lookback_days=300,
        minimum_training_days=210,
        minimum_replay_days=90,
        walk_forward_window_days=90,
        confidence_label="quickstart",
        historical_sources=("massive",),
        context_sources=("coinbase", "jupiter"),
    ),
    "full_730d": PaperPracticeTrainingProfile(
        name="full_730d",
        history_lookback_days=730,
        minimum_training_days=365,
        minimum_replay_days=90,
        walk_forward_window_days=90,
        confidence_label="full",
        historical_sources=("massive",),
        context_sources=("coinbase", "jupiter"),
    ),
}


def list_training_profiles() -> dict[str, PaperPracticeTrainingProfile]:
    return dict(_PROFILE_CATALOG)


def _serialize_profile(profile: PaperPracticeTrainingProfile, *, available_history_days: int) -> dict[str, Any]:
    required_history_days = profile.required_history_days
    return {
        "name": profile.name,
        "history_lookback_days": profile.history_lookback_days,
        "minimum_training_days": profile.minimum_training_days,
        "minimum_replay_days": profile.minimum_replay_days,
        "walk_forward_window_days": profile.walk_forward_window_days,
        "required_history_days": required_history_days,
        "available_history_days": available_history_days,
        "confidence_label": profile.confidence_label,
        "historical_sources": list(profile.historical_sources),
        "context_sources": list(profile.context_sources),
        "ready": available_history_days >= required_history_days,
        "shortfall_days": max(required_history_days - available_history_days, 0),
    }


def summarize_training_profile_readiness(
    available_history_days: int,
    selected_profile_name: str,
) -> dict[str, Any]:
    normalized_available_days = max(int(available_history_days), 0)
    profiles = {
        name: _serialize_profile(profile, available_history_days=normalized_available_days)
        for name, profile in sorted(
            _PROFILE_CATALOG.items(),
            key=lambda item: item[1].required_history_days,
        )
    }
    strongest_ready_name = ""
    for name, profile_summary in sorted(
        profiles.items(),
        key=lambda item: item[1]["required_history_days"],
        reverse=True,
    ):
        if profile_summary["ready"]:
            strongest_ready_name = name
            break

    if selected_profile_name == "auto":
        resolved_profile_name = strongest_ready_name or min(
            profiles.items(),
            key=lambda item: item[1]["required_history_days"],
        )[0]
    else:
        if selected_profile_name not in profiles:
            raise ValueError(
                f"Unknown paper-practice training profile `{selected_profile_name}`. "
                f"Expected one of: {', '.join(['auto', *profiles.keys()])}."
            )
        resolved_profile_name = selected_profile_name

    return {
        "requested_profile_name": selected_profile_name,
        "selected_profile_name": resolved_profile_name,
        "available_history_days": normalized_available_days,
        "best_ready_profile_name": strongest_ready_name,
        "profiles": profiles,
    }


def get_training_profile(
    profile_name: str,
    *,
    available_history_days: int | None = None,
) -> PaperPracticeTrainingProfile:
    if profile_name == "auto":
        if available_history_days is None:
            raise ValueError("`available_history_days` is required when resolving the `auto` training profile.")
        readiness = summarize_training_profile_readiness(
            available_history_days=available_history_days,
            selected_profile_name="auto",
        )
        profile_name = str(readiness["selected_profile_name"])

    try:
        return _PROFILE_CATALOG[profile_name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown paper-practice training profile `{profile_name}`. "
            f"Expected one of: {', '.join(['auto', *_PROFILE_CATALOG.keys()])}."
        ) from exc


def assess_training_history_window(
    *,
    history_start: pd.Timestamp,
    history_end: pd.Timestamp,
    profile: PaperPracticeTrainingProfile,
) -> dict[str, Any]:
    if history_end < history_start:
        available_history_days = 0
    else:
        available_history_days = int((history_end - history_start).days) + 1

    replay_available_days = max(available_history_days - profile.minimum_training_days, 0)
    required_history_days = profile.required_history_days
    ready = available_history_days >= required_history_days
    return {
        "profile_name": profile.name,
        "history_start": history_start.date().isoformat(),
        "history_end": history_end.date().isoformat(),
        "available_history_days": available_history_days,
        "minimum_training_days": profile.minimum_training_days,
        "minimum_replay_days": profile.minimum_replay_days,
        "walk_forward_window_days": profile.walk_forward_window_days,
        "required_history_days": required_history_days,
        "replay_available_days": replay_available_days,
        "ready": ready,
        "shortfall_days": max(required_history_days - available_history_days, 0),
        "confidence_label": profile.confidence_label,
    }
