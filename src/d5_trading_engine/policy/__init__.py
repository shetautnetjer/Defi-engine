"""Policy surfaces and data paths for strategy eligibility and decision tracing."""

from __future__ import annotations

from pathlib import Path

GLOBAL_REGIME_V1_BIAS_MAP = Path(__file__).with_name("global_regime_v1_bias_map.yaml")

__all__ = ["GLOBAL_REGIME_V1_BIAS_MAP"]
