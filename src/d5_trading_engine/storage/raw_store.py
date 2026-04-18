"""
D5 Trading Engine — Raw Data Store

Writes raw API responses to the file system as JSONL.
Files land in data/raw/{provider}/{YYYY-MM-DD}/ partitions.
Atomic writes via temp file + rename.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import orjson

from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.common.logging import get_logger
from d5_trading_engine.common.time_utils import date_partition, to_iso, utcnow

log = get_logger(__name__)


class RawStore:
    """Write raw API responses to JSONL files.

    File layout:
        data/raw/{provider}/{YYYY-MM-DD}/{capture_type}_{timestamp}.jsonl

    Each line is a complete JSON object with metadata envelope.
    """

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def _partition_dir(self, provider: str, partition: str | None = None) -> Path:
        """Get or create the partition directory for a provider.

        Args:
            provider: Provider name (jupiter, helius, fred, massive).
            partition: Date partition string (defaults to today).

        Returns:
            Path to the partition directory.
        """
        partition = partition or date_partition()
        d = self.settings.raw_dir / provider / partition
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_jsonl(
        self,
        provider: str,
        capture_type: str,
        records: list[dict],
        ingest_run_id: str | None = None,
        *,
        partition: str | None = None,
    ) -> Path:
        """Write records to a JSONL file atomically.

        Each record is wrapped in a metadata envelope:
        {
            "provider": "...",
            "capture_type": "...",
            "ingest_run_id": "...",
            "captured_at": "...",
            "payload": { ... original record ... }
        }

        Args:
            provider: Provider name.
            capture_type: Type of capture (e.g. "token_list", "prices").
            records: List of raw response dicts.
            ingest_run_id: Optional ingest run ID for lineage.

        Returns:
            Path to the written file.
        """
        if not records:
            log.warning("raw_store_empty", provider=provider, capture_type=capture_type)
            return Path()

        partition_dir = self._partition_dir(provider, partition=partition)
        now = utcnow()
        filename = f"{capture_type}_{now.strftime('%H%M%S')}_{os.getpid()}.jsonl"
        target = partition_dir / filename

        # Atomic write: write to temp, then rename
        fd, tmp_path = tempfile.mkstemp(dir=str(partition_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                for record in records:
                    envelope = {
                        "provider": provider,
                        "capture_type": capture_type,
                        "ingest_run_id": ingest_run_id,
                        "captured_at": to_iso(now),
                        "payload": record,
                    }
                    f.write(orjson.dumps(envelope))
                    f.write(b"\n")
            os.rename(tmp_path, str(target))
        except Exception:
            # Clean up temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        log.info(
            "raw_store_written",
            provider=provider,
            capture_type=capture_type,
            path=str(target),
            records=len(records),
        )
        return target

    def write_single(
        self,
        provider: str,
        capture_type: str,
        payload: dict,
        ingest_run_id: str | None = None,
        *,
        partition: str | None = None,
    ) -> Path:
        """Write a single payload record.

        Convenience wrapper around write_jsonl for single-record writes.

        Args:
            provider: Provider name.
            capture_type: Type of capture.
            payload: Single raw response dict.
            ingest_run_id: Optional ingest run ID.

        Returns:
            Path to the written file.
        """
        return self.write_jsonl(
            provider,
            capture_type,
            [payload],
            ingest_run_id,
            partition=partition,
        )

    def write_bytes(
        self,
        provider: str,
        capture_type: str,
        content: bytes,
        *,
        suffix: str,
        partition: str | None = None,
    ) -> Path:
        """Write raw bytes atomically for replayable flat-file captures."""
        if not content:
            log.warning("raw_store_bytes_empty", provider=provider, capture_type=capture_type)
            return Path()

        partition_dir = self._partition_dir(provider, partition=partition)
        now = utcnow()
        filename = f"{capture_type}_{now.strftime('%H%M%S')}_{os.getpid()}{suffix}"
        target = partition_dir / filename

        fd, tmp_path = tempfile.mkstemp(dir=str(partition_dir), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)
            os.rename(tmp_path, str(target))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        log.info(
            "raw_store_bytes_written",
            provider=provider,
            capture_type=capture_type,
            path=str(target),
            size_bytes=len(content),
        )
        return target
