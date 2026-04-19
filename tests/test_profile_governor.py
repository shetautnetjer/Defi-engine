from __future__ import annotations

from d5_trading_engine.research_loop.profile_governor import (
    GovernorCandidate,
    ProfileGovernor,
    load_profile_governor_policy,
)


def test_load_profile_governor_policy_from_repo_ai_surface(settings) -> None:
    policy = load_profile_governor_policy(settings.repo_root)

    assert policy.policy_id == "profile_router_policy_v1"
    assert policy.thresholds.min_select_score == 70.0
    assert "SELECT_PROFILE" in policy.actions


def test_profile_governor_selects_confirmed_top_candidate(settings) -> None:
    governor = ProfileGovernor(repo_root=settings.repo_root)
    candidates = [
        GovernorCandidate(
            candidate_id="proposal_high",
            profile_name="execution_cost_minimizer",
            evidence_maturity="paper_cycle",
            out_of_sample_score=82.0,
            paper_score=88.0,
            stability_score=78.0,
            regime_fit_score=86.0,
            cost_penalty=8.0,
            decay_penalty=4.0,
            complexity_penalty=2.0,
            disagreement_index=0.08,
            eligible_for_selection=True,
            profile_neutral_validation_state="confirmed",
        ),
        GovernorCandidate(
            candidate_id="proposal_low",
            profile_name="risk_off_defensive",
            evidence_maturity="strategy_eval",
            out_of_sample_score=58.0,
            paper_score=35.0,
            stability_score=54.0,
            regime_fit_score=52.0,
            cost_penalty=9.0,
            decay_penalty=6.0,
            complexity_penalty=4.0,
            disagreement_index=0.08,
            eligible_for_selection=True,
            profile_neutral_validation_state="confirmed",
        ),
    ]

    result = governor.evaluate_candidates(
        candidates,
        selected_research_profile_name="execution_cost_minimizer",
    )

    assert result["governor_action"] == "SELECT_PROFILE"
    assert result["selected_candidate_id"] == "proposal_high"
    assert result["selected_profile_name"] == "execution_cost_minimizer"
    assert result["governor_scorecard"]["candidate_count"] == 2


def test_profile_governor_blends_close_confirmed_candidates(settings) -> None:
    governor = ProfileGovernor(repo_root=settings.repo_root)
    candidates = [
        GovernorCandidate(
            candidate_id="proposal_a",
            profile_name="wallet_flow_follower",
            evidence_maturity="paper_cycle",
            out_of_sample_score=81.0,
            paper_score=84.0,
            stability_score=74.0,
            regime_fit_score=80.0,
            cost_penalty=9.0,
            decay_penalty=4.0,
            complexity_penalty=4.0,
            disagreement_index=0.12,
            eligible_for_selection=True,
            profile_neutral_validation_state="confirmed",
        ),
        GovernorCandidate(
            candidate_id="proposal_b",
            profile_name="breakout_intraday_solana",
            evidence_maturity="paper_cycle",
            out_of_sample_score=79.0,
            paper_score=83.0,
            stability_score=73.0,
            regime_fit_score=79.0,
            cost_penalty=9.0,
            decay_penalty=4.0,
            complexity_penalty=4.0,
            disagreement_index=0.12,
            eligible_for_selection=True,
            profile_neutral_validation_state="confirmed",
        ),
    ]

    result = governor.evaluate_candidates(
        candidates,
        selected_research_profile_name="wallet_flow_follower",
    )

    assert result["governor_action"] == "BLEND_PROFILES"
    assert result["blend_candidate_ids"] == ["proposal_a", "proposal_b"]


def test_profile_governor_uses_no_trade_for_high_disagreement(settings) -> None:
    governor = ProfileGovernor(repo_root=settings.repo_root)
    candidates = [
        GovernorCandidate(
            candidate_id="proposal_conflicted",
            profile_name="momentum_scalper_perps",
            evidence_maturity="paper_cycle",
            out_of_sample_score=92.0,
            paper_score=90.0,
            stability_score=65.0,
            regime_fit_score=91.0,
            cost_penalty=8.0,
            decay_penalty=3.0,
            complexity_penalty=2.0,
            disagreement_index=0.48,
            eligible_for_selection=True,
            profile_neutral_validation_state="confirmed",
        )
    ]

    result = governor.evaluate_candidates(
        candidates,
        selected_research_profile_name="momentum_scalper_perps",
    )

    assert result["governor_action"] == "NO_TRADE"
    assert "high_profile_disagreement" in result["governor_reason_codes"]
