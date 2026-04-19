"""Template-backed QMD rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from d5_trading_engine.common.time_utils import utcnow

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _normalize_frontmatter_value(value: Any) -> Any:
    """Normalize metadata into YAML-safe scalar/list/dict values."""
    if value is None:
        return None
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    if isinstance(value, dict):
        normalized = {
            str(key): _normalize_frontmatter_value(item)
            for key, item in value.items()
            if item is not None
        }
        return normalized or None
    if isinstance(value, (list, tuple, set)):
        normalized_items = [
            item
            for item in (_normalize_frontmatter_value(item) for item in value)
            if item is not None
        ]
        return normalized_items or None
    return value


def _build_frontmatter(metadata: dict[str, Any]) -> str:
    """Render deterministic YAML frontmatter for QMD packets."""
    normalized = {
        str(key): value
        for key, raw_value in metadata.items()
        if (value := _normalize_frontmatter_value(raw_value)) is not None
    }
    serialized = yaml.safe_dump(
        normalized,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    ).strip()
    return f"---\n{serialized}\n---"


def trading_report_metadata(
    *,
    report_kind: str,
    run_id: str | None = None,
    owner_type: str | None = None,
    owner_key: str | None = None,
    profile_revision_id: str | None = None,
    instrument_scope: Iterable[str] | None = None,
    context_instruments: Iterable[str] | None = None,
    timeframe: str | None = None,
    summary_path: str | Path | None = None,
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Build the canonical small trading frontmatter payload for QMD evidence."""
    return {
        "report_kind": report_kind,
        "run_id": run_id,
        "owner_type": owner_type,
        "owner_key": owner_key,
        "profile_revision_id": profile_revision_id,
        "instrument_scope": list(instrument_scope or []),
        "context_instruments": list(context_instruments or []),
        "timeframe": timeframe,
        "summary_path": str(summary_path) if summary_path is not None else None,
        "config_path": str(config_path) if config_path is not None else None,
    }


def render_qmd(
    template_name: str,
    *,
    title: str,
    summary_lines: Iterable[str],
    sections: Iterable[tuple[str, Iterable[str]]],
    generated_at=None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Render a lightweight QMD report from the named template."""
    template = (_TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    generated = generated_at or utcnow()
    summary_block = "\n".join(summary_lines) or "- no summary provided"

    body_chunks: list[str] = []
    for heading, lines in sections:
        body_chunks.extend([f"## {heading}", "", *list(lines), ""])

    body_sections = "\n".join(body_chunks).strip()
    if not body_sections:
        body_sections = "## Details\n\n- no additional details"

    frontmatter = _build_frontmatter(
        {
            "title": title,
            "date": generated,
            "format": "gfm",
            **(metadata or {}),
        }
    )
    return (
        template.replace("{{frontmatter}}", frontmatter)
        .replace("{{summary_block}}", summary_block)
        .replace("{{body_sections}}", body_sections)
    )
