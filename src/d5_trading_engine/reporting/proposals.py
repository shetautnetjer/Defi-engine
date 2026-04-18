"""Improvement proposal truth helpers."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.common.time_utils import utcnow
from d5_trading_engine.config.settings import Settings, get_settings
from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.reporting.qmd import render_qmd
from d5_trading_engine.storage.truth.engine import get_session
from d5_trading_engine.storage.truth.models import ImprovementProposalV1


def create_improvement_proposal(
    *,
    artifact_dir: Path,
    proposal_kind: str,
    source_owner_type: str,
    source_owner_key: str,
    governance_scope: str,
    title: str,
    summary: str,
    hypothesis: str,
    next_test: str,
    metrics: dict[str, Any] | None = None,
    reason_codes: list[str] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Persist an advisory-only proposal row plus its QMD evidence packet."""
    resolved_settings = settings or get_settings()
    proposal_id = f"proposal_{proposal_kind}_{uuid.uuid4().hex[:12]}"
    metrics_payload = metrics or {}
    reason_codes_payload = reason_codes or []
    created_at = utcnow()

    session = get_session(resolved_settings)
    try:
        session.add(
            ImprovementProposalV1(
                proposal_id=proposal_id,
                proposal_kind=proposal_kind,
                source_owner_type=source_owner_type,
                source_owner_key=source_owner_key,
                governance_scope=governance_scope,
                status="proposed",
                runtime_effect="advisory_only",
                title=title,
                summary=summary,
                hypothesis=hypothesis,
                next_test=next_test,
                metrics_json=orjson.dumps(metrics_payload).decode(),
                reason_codes_json=orjson.dumps(reason_codes_payload).decode(),
                created_at=created_at,
            )
        )
        session.commit()
    finally:
        session.close()

    payload = {
        "proposal_id": proposal_id,
        "proposal_kind": proposal_kind,
        "source_owner_type": source_owner_type,
        "source_owner_key": source_owner_key,
        "governance_scope": governance_scope,
        "status": "proposed",
        "runtime_effect": "advisory_only",
        "title": title,
        "summary": summary,
        "hypothesis": hypothesis,
        "next_test": next_test,
        "metrics": metrics_payload,
        "reason_codes": reason_codes_payload,
        "created_at": created_at.isoformat(),
    }

    write_json_artifact(
        artifact_dir / "proposal.json",
        payload,
        owner_type="proposal",
        owner_key=proposal_id,
        artifact_type="improvement_proposal",
        settings=resolved_settings,
        metadata={"source_owner_type": source_owner_type, "source_owner_key": source_owner_key},
    )
    write_text_artifact(
        artifact_dir / "proposal.qmd",
        render_qmd(
            "proposal.qmd",
            title=title,
            summary_lines=[
                f"- proposal id: `{proposal_id}`",
                f"- source owner: `{source_owner_type}:{source_owner_key}`",
                f"- governance scope: `{governance_scope}`",
                "- runtime effect: `advisory_only`",
                f"- status: `proposed`",
            ],
            sections=[
                ("Summary", [summary]),
                ("Hypothesis", [hypothesis]),
                ("Metrics", [f"- `{key}`: `{value}`" for key, value in sorted(metrics_payload.items())] or ["- none recorded"]),
                ("Reason Codes", [f"- `{item}`" for item in reason_codes_payload] or ["- none supplied"]),
                ("Next Test", [next_test]),
            ],
            generated_at=created_at,
        ),
        owner_type="proposal",
        owner_key=proposal_id,
        artifact_type="improvement_proposal_qmd",
        artifact_format="qmd",
        settings=resolved_settings,
        metadata={"source_owner_type": source_owner_type, "source_owner_key": source_owner_key},
    )
    return payload
