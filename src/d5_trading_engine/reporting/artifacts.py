"""Artifact writing plus canonical SQL receipts."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import ArtifactReference

JSON_OPTIONS = orjson.OPT_INDENT_2 | orjson.OPT_SERIALIZE_NUMPY


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def record_artifact_reference(
    *,
    settings: Settings | None = None,
    owner_type: str,
    owner_key: str,
    artifact_type: str,
    artifact_format: str,
    artifact_path: Path,
    content: bytes,
    metadata: dict[str, Any] | None = None,
) -> ArtifactReference:
    """Persist an artifact receipt in canonical SQL truth."""
    resolved_settings = settings or get_settings()
    session = get_session(resolved_settings)
    try:
        row = ArtifactReference(
            owner_type=owner_type,
            owner_key=owner_key,
            artifact_type=artifact_type,
            artifact_format=artifact_format,
            artifact_path=str(artifact_path),
            content_sha256=_sha256(content),
            metadata_json=(
                orjson.dumps(metadata, option=JSON_OPTIONS).decode()
                if metadata is not None
                else None
            ),
            created_at=utcnow(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row
    finally:
        session.close()


def write_json_artifact(
    path: Path,
    payload: Any,
    *,
    owner_type: str,
    owner_key: str,
    artifact_type: str,
    settings: Settings | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a JSON artifact and record its SQL receipt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = orjson.dumps(payload, option=JSON_OPTIONS)
    path.write_bytes(content)
    record_artifact_reference(
        settings=settings,
        owner_type=owner_type,
        owner_key=owner_key,
        artifact_type=artifact_type,
        artifact_format="json",
        artifact_path=path,
        content=content,
        metadata=metadata,
    )
    return path


def write_text_artifact(
    path: Path,
    content: str,
    *,
    owner_type: str,
    owner_key: str,
    artifact_type: str,
    artifact_format: str,
    settings: Settings | None = None,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a text artifact and record its SQL receipt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    path.write_bytes(encoded)
    record_artifact_reference(
        settings=settings,
        owner_type=owner_type,
        owner_key=owner_key,
        artifact_type=artifact_type,
        artifact_format=artifact_format,
        artifact_path=path,
        content=encoded,
        metadata=metadata,
    )
    return path
