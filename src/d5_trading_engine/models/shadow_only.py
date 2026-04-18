"""Shadow-only model registry.

These entries are visible to research and reporting layers but are not
runtime-eligible in v1.
"""

from __future__ import annotations

SHADOW_ONLY_MODELS = {
    "chronos_2": {
        "status": "shadow_only",
        "runtime_eligible": False,
        "notes": "Forecasting sidecar for scenario generation only.",
    },
    "monte_carlo": {
        "status": "shadow_only",
        "runtime_eligible": False,
        "notes": "Scenario fan-out for evidence packets only.",
    },
    "hawkes": {
        "status": "shadow_only",
        "runtime_eligible": False,
        "notes": "Future microstructure research seam.",
    },
    "hurst": {
        "status": "shadow_only",
        "runtime_eligible": False,
        "notes": "Future persistence/mean-reversion research seam.",
    },
    "tda": {
        "status": "shadow_only",
        "runtime_eligible": False,
        "notes": "Future topology-aware research seam.",
    },
    "meta_label_stacks": {
        "status": "shadow_only",
        "runtime_eligible": False,
        "notes": "Richer ensemble stacks remain advisory-only until explicitly approved.",
    },
}
