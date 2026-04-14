"""
D5 Trading Engine — Error Hierarchy

All custom exceptions inherit from D5Error for clean exception handling.
"""

from __future__ import annotations


class D5Error(Exception):
    """Base error for all D5 trading engine exceptions."""


class ConfigError(D5Error):
    """Configuration-related errors (missing keys, bad values)."""


class AdapterError(D5Error):
    """Errors from external data provider adapters."""

    def __init__(self, provider: str, message: str, status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        detail = f"[{provider}] {message}"
        if status_code:
            detail = f"{detail} (HTTP {status_code})"
        super().__init__(detail)


class CaptureError(D5Error):
    """Errors during data capture orchestration."""


class NormalizeError(D5Error):
    """Errors during raw → canonical normalization."""


class StorageError(D5Error):
    """Errors in storage layer (DB, file I/O)."""


class FeatureError(D5Error):
    """Errors during deterministic feature materialization."""
