from __future__ import annotations

from pathlib import Path

from d5_trading_engine.research_loop.research_profiles import (
    get_research_profile,
    load_research_profile_catalog,
    summarize_research_profile,
)


def test_load_research_profile_catalog_from_repo_ai_surface(settings) -> None:
    catalog = load_research_profile_catalog(settings.repo_root)

    assert catalog.meta.version == "v1"
    assert "execution_cost_minimizer" in catalog.profiles


def test_get_research_profile_and_summary(settings) -> None:
    profile = get_research_profile("execution_cost_minimizer", repo_root=settings.repo_root)
    summary = summarize_research_profile(profile)

    assert profile.name == "execution_cost_minimizer"
    assert summary["name"] == "execution_cost_minimizer"
    assert "execution / intraday" in summary["summary"]
    assert "jupiter" in summary["preferred_sources"]

