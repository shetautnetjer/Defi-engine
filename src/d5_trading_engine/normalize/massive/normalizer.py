"""
D5 Trading Engine — Massive Normalizer (Scaffold)

Massive data is raw-only in v0.
Normalization depends on discovering the actual response shapes
from the Massive API under the current plan's entitlements.

TODO: Implement once Massive endpoints are tested and response shapes are known.
"""

from __future__ import annotations

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger

log = get_logger(__name__, normalizer="massive")


class MassiveNormalizer:
    """Massive data normalizer (scaffold).

    In v0, Massive data is stored raw-only.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def normalize_crypto_event(self, event: dict, ingest_run_id: str) -> int:
        """Normalize a Massive crypto event.

        Currently a no-op — data is stored raw by the capture runner.

        Args:
            event: Raw event dict.
            ingest_run_id: Ingest run ID.

        Returns:
            0 (no canonical normalization in v0).
        """
        log.debug("massive_normalize_noop", detail="Raw-only in v0")
        return 0
