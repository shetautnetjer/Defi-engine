from __future__ import annotations

from pathlib import Path

from d5_trading_engine.reporting.artifacts import write_json_artifact, write_text_artifact
from d5_trading_engine.storage.truth.engine import get_session, run_migrations_to_head
from d5_trading_engine.storage.truth.models import ArtifactReference


def test_reporting_artifacts_write_sql_receipts(settings) -> None:
    run_migrations_to_head(settings)
    artifact_dir = settings.data_dir / "research" / "artifacts_test"

    json_path = write_json_artifact(
        artifact_dir / "sample.json",
        {"hello": "world"},
        owner_type="test_owner",
        owner_key="owner_001",
        artifact_type="sample_json",
        settings=settings,
    )
    qmd_path = write_text_artifact(
        artifact_dir / "sample.qmd",
        "# Sample\n",
        owner_type="test_owner",
        owner_key="owner_001",
        artifact_type="sample_qmd",
        artifact_format="qmd",
        settings=settings,
    )

    assert json_path == artifact_dir / "sample.json"
    assert qmd_path == artifact_dir / "sample.qmd"
    assert json_path.exists()
    assert qmd_path.exists()

    session = get_session(settings)
    try:
        rows = (
            session.query(ArtifactReference)
            .filter_by(owner_type="test_owner", owner_key="owner_001")
            .order_by(ArtifactReference.id.asc())
            .all()
        )
    finally:
        session.close()

    assert [row.artifact_type for row in rows] == ["sample_json", "sample_qmd"]
    assert all(Path(row.artifact_path).exists() for row in rows)
    assert all(row.content_sha256 for row in rows)
