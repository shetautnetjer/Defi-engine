from __future__ import annotations

from datetime import UTC, datetime

from d5_trading_engine.reporting.qmd import render_qmd, trading_report_metadata


def test_render_qmd_includes_trading_frontmatter_metadata() -> None:
    rendered = render_qmd(
        "experiment_run.qmd",
        title="paper practice backtest walk-forward",
        metadata=trading_report_metadata(
            report_kind="paper_practice_backtest",
            run_id="backtest_walk_forward_fixture",
            owner_type="paper_practice_backtest",
            owner_key="backtest_walk_forward_fixture",
            profile_revision_id="paper_profile_revision_fixture",
            instrument_scope=["SOL/USDC"],
            context_instruments=["BTC/USD", "ETH/USD"],
            timeframe="15m",
            summary_path="summary.json",
            config_path="config.json",
        ),
        summary_lines=["- status: `completed`"],
        sections=[("Bounded Next Change", ["- keep"])],
        generated_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
    )

    assert rendered.startswith("---\n")
    assert "title: paper practice backtest walk-forward" in rendered
    assert "report_kind: paper_practice_backtest" in rendered
    assert "run_id: backtest_walk_forward_fixture" in rendered
    assert "owner_type: paper_practice_backtest" in rendered
    assert "profile_revision_id: paper_profile_revision_fixture" in rendered
    assert "instrument_scope:\n- SOL/USDC" in rendered
    assert "context_instruments:\n- BTC/USD\n- ETH/USD" in rendered
    assert "summary_path: summary.json" in rendered
    assert "config_path: config.json" in rendered
    assert "# Summary" in rendered
    assert "## Bounded Next Change" in rendered
