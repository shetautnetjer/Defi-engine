"""Policy surfaces and data paths for strategy eligibility and decision tracing."""

from __future__ import annotations

from pathlib import Path

from d5_trading_engine.policy.global_regime_v1 import (
    GlobalRegimePolicyEvaluator,
    load_global_regime_policy_config,
)

GLOBAL_REGIME_V1_BIAS_MAP = Path(__file__).with_name("global_regime_v1_bias_map.yaml")

__all__ = [
    "GLOBAL_REGIME_V1_BIAS_MAP",
    "GlobalRegimePolicyEvaluator",
    "load_global_regime_policy_config",
]
