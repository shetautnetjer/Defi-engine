"""Machine-readable registries for bounded research configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

CANONICAL_DIRECTION_LABEL_SPECS: dict[str, dict[str, float | int]] = {
    "direction_60m_v1": {
        "horizon_bars": 12,
        "atr_multiple": 1.0,
        "low_confidence_threshold": 0.55,
    },
    "direction_240m_v1": {
        "horizon_bars": 48,
        "atr_multiple": 1.0,
        "low_confidence_threshold": 0.55,
    },
}

def load_yaml_registry(repo_root: Path, filename: str) -> dict[str, Any]:
    path = repo_root / ".ai" / "swarm" / filename
    if not path.exists():
        raise RuntimeError(f"Missing machine-readable swarm registry: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"Registry {path} must decode to an object.")
    return data


def load_story_classes(repo_root: Path) -> dict[str, Any]:
    return load_yaml_registry(repo_root, "story_classes.yaml")


def load_metrics_registry(repo_root: Path) -> dict[str, Any]:
    return load_yaml_registry(repo_root, "metrics_registry.yaml")


def load_strategy_registry(repo_root: Path) -> dict[str, Any]:
    return load_yaml_registry(repo_root, "strategy_registry.yaml")


def load_instrument_scope(repo_root: Path) -> dict[str, Any]:
    return load_yaml_registry(repo_root, "instrument_scope.yaml")
