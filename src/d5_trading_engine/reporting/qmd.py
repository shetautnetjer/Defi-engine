"""Template-backed QMD rendering."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from d5_trading_engine.common.time_utils import utcnow

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def render_qmd(
    template_name: str,
    *,
    title: str,
    summary_lines: Iterable[str],
    sections: Iterable[tuple[str, Iterable[str]]],
    generated_at=None,
) -> str:
    """Render a lightweight QMD report from the named template."""
    template = (_TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    summary_block = "\n".join(summary_lines) or "- no summary provided"

    body_chunks: list[str] = []
    for heading, lines in sections:
        body_chunks.extend([f"## {heading}", "", *list(lines), ""])

    body_sections = "\n".join(body_chunks).strip()
    if not body_sections:
        body_sections = "## Details\n\n- no additional details"

    return (
        template.replace("{{title}}", title)
        .replace("{{generated_at}}", (generated_at or utcnow()).isoformat())
        .replace("{{summary_block}}", summary_block)
        .replace("{{body_sections}}", body_sections)
    )
