from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "README.md",
    REPO_ROOT / "docs" / "project" / "bootstrap_inventory.md",
    REPO_ROOT / "docs" / "project" / "current_runtime_truth.md",
    REPO_ROOT / "docs" / "prd" / "crypto_backtesting_mission.md",
    REPO_ROOT / "docs" / "prd" / "backtesting_completion_definition.md",
    REPO_ROOT / "docs" / "task" / "source_expansion_preconditions.md",
    REPO_ROOT / "docs" / "plans" / "source_expansion_preconditions.md",
    REPO_ROOT / "docs" / "plans" / "historical_research_protocol.md",
    REPO_ROOT / "docs" / "plans" / "strategy_descent_and_instrument_scope.md",
    REPO_ROOT / "docs" / "task" / "bootstrap_truth_sync.md",
    REPO_ROOT / "docs" / "architecture" / "bootstrap_architecture.md",
    REPO_ROOT / "docs" / "architecture" / "backtest_truth_contract.md",
    REPO_ROOT / "docs" / "runbooks" / "first_capture.md",
    REPO_ROOT / "docs" / "runbooks" / "feature_condition_shadow_cycle.md",
    REPO_ROOT / "docs" / "runbooks" / "ralph_tmux_swarm.md",
    REPO_ROOT / "docs" / "math" / "regime_shadow_modeling_contracts.md",
    REPO_ROOT / "docs" / "math" / "market_regime_forecast_and_labeling_program.md",
    REPO_ROOT / "docs" / "policy" / "runtime_authority_and_promotion_ladder.md",
    REPO_ROOT / "docs" / "policy" / "writer_story_promotion_rubric.md",
    REPO_ROOT / "docs" / "test" / "bootstrap_validation.md",
]
REQUIRED_DOCS = ACTIVE_DOCS + [
    REPO_ROOT / "docs" / "issues" / "governed_product_descent_capability_ladder.md",
    REPO_ROOT / "docs" / "gaps" / "bootstrap_gap_register.md",
    REPO_ROOT / "docs" / "gaps" / "backtest_truth_model_gap.md",
    REPO_ROOT / "docs" / "gaps" / "label_program_and_regime_taxonomy_gap.md",
    REPO_ROOT / "docs" / "gaps" / "strategy_registry_and_challenger_framework_gap.md",
    REPO_ROOT / "docs" / "gaps" / "execution_intent_gap.md",
    REPO_ROOT / "docs" / "gaps" / "instrument_expansion_readiness_gap.md",
    REPO_ROOT / "docs" / "gaps" / "tmux_machine_law_and_packet_gap.md",
    REPO_ROOT / "docs" / "handoff" / "2026-04-12_bootstrap_phase_1.md",
]


def test_single_root_env_template_exists() -> None:
    assert (REPO_ROOT / ".env.example").exists()
    assert not (REPO_ROOT / "env.example").exists()


def test_required_bootstrap_docs_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not path.exists()]
    assert not missing


def test_active_docs_do_not_reference_stale_cli_strings() -> None:
    stale_strings = [
        "d5 init-db",
        "Base.metadata.create_all()",
        "create the current SQLite schema from ORM metadata",
        "there is no `tests/` directory yet",
    ]

    for path in ACTIVE_DOCS:
        contents = path.read_text()
        for stale in stale_strings:
            assert stale not in contents, f"found stale text {stale!r} in {path}"


def test_ralph_runbook_mentions_persistent_supervision() -> None:
    runbook = (REPO_ROOT / "docs" / "runbooks" / "ralph_tmux_swarm.md").read_text()
    assert "start_supervisor.sh" in runbook
    assert "supervisor_status.sh" in runbook
    assert "health_swarm.sh" in runbook
    assert "refresh_watch_swarm.sh" in runbook
    assert "relaunch_stale_lanes.sh" in runbook
    assert "run_persistent_cycle.sh" in runbook
    assert "mailbox.jsonl" in runbook
    assert "stops both the detached supervisor and the tmux session" in runbook
    assert "session control only" in runbook
    assert "lane-health" in runbook
    assert "accepted_receipts" in runbook
    assert "detached supervisor state" in runbook
    assert "alive" in runbook
    assert "producing" in runbook
    assert "accepted" in runbook
    assert "mailbox_current.json" in runbook
    assert "finder_state.json" in runbook
    assert "finder_decision.json" in runbook
    assert "architecture-finder" in runbook
    assert "research-finder" in runbook
    assert "swarmState" in runbook
    assert "completionAuditState" in runbook
    assert "terminal_complete" in runbook
    assert "audit_followons_present" in runbook
    assert ".ai/swarm/swarm.yaml" in runbook
    assert "policy-only" in runbook


def test_north_star_docs_define_scope_and_governance() -> None:
    mission = (REPO_ROOT / "docs" / "prd" / "crypto_backtesting_mission.md").read_text()
    completion = (
        REPO_ROOT / "docs" / "prd" / "backtesting_completion_definition.md"
    ).read_text()
    scope = (
        REPO_ROOT / "docs" / "plans" / "strategy_descent_and_instrument_scope.md"
    ).read_text()
    math_program = (
        REPO_ROOT / "docs" / "math" / "market_regime_forecast_and_labeling_program.md"
    ).read_text()
    authority = (
        REPO_ROOT / "docs" / "policy" / "runtime_authority_and_promotion_ladder.md"
    ).read_text()
    writer_rubric = (
        REPO_ROOT / "docs" / "policy" / "writer_story_promotion_rubric.md"
    ).read_text()

    assert "paper-first" in mission
    assert "Solana-first" in mission
    assert "Jupiter perps" in scope
    assert "Coinbase futures" in scope
    assert "future-stage" in scope
    assert "`up`" in math_program
    assert "`down`" in math_program
    assert "`flat`" in math_program
    assert "Chronos-2" in math_program
    assert "Monte Carlo" in math_program
    assert "Fibonacci" in math_program
    assert "advisory" in authority
    assert "writer-integrator" in authority
    assert "docs/issues/" in writer_rubric
    assert "docs/gaps/" in writer_rubric
    assert "best next governed slice" in writer_rubric
    assert "terminal_complete" in completion


def test_current_runtime_truth_and_ai_packet_reference_machine_readable_swarm_law() -> None:
    runtime_truth = (REPO_ROOT / "docs" / "project" / "current_runtime_truth.md").read_text()
    ai_readme = (REPO_ROOT / ".ai" / "README.md").read_text()
    repo_map = (REPO_ROOT / ".ai" / "index" / "current_repo_map.md").read_text()
    backtest_arch = (
        REPO_ROOT / "docs" / "architecture" / "backtest_truth_contract.md"
    ).read_text()

    assert "execution intent" in runtime_truth.lower()
    assert "backtest" in runtime_truth.lower()
    assert "Stage 1" in runtime_truth
    assert "current truth consolidation" in runtime_truth
    assert ".ai/swarm/" in ai_readme
    assert "policy-only" in ai_readme
    assert ".ai/swarm/swarm.yaml" in repo_map
    assert "BacktestTruthOwner" in backtest_arch
    assert "spot-first" in backtest_arch


def test_stage_one_issue_and_gap_guides_exist_for_future_handoffs() -> None:
    issue_guide = (
        REPO_ROOT / "docs" / "issues" / "governed_product_descent_capability_ladder.md"
    ).read_text()
    gaps_index = (REPO_ROOT / "docs" / "gaps" / "bootstrap_gap_register.md").read_text()

    assert "current truth consolidation" in issue_guide
    assert "backtesting truth layer" in issue_guide
    assert "governed promotion ladder" in issue_guide
    assert "Solana-first" in issue_guide
    assert "backtest_truth_model_gap.md" in gaps_index
    assert "execution_intent_gap.md" in gaps_index


def test_stale_underclaims_are_removed_from_current_truth_docs() -> None:
    mission = (REPO_ROOT / "docs" / "prd" / "crypto_backtesting_mission.md").read_text()
    runbook = (
        REPO_ROOT / "docs" / "runbooks" / "feature_condition_shadow_cycle.md"
    ).read_text()
    math_contract = (
        REPO_ROOT / "docs" / "math" / "regime_shadow_modeling_contracts.md"
    ).read_text()
    bootstrap_gaps = (REPO_ROOT / "docs" / "gaps" / "bootstrap_gap_register.md").read_text()

    assert "continuous capture ownership across the required lanes" not in mission
    assert "realized-feedback comparison between `research_loop/` and paper outcomes" not in mission
    assert "policy-owned trade eligibility" not in runbook
    assert "paper-session ownership" not in runbook
    assert "The repo does not yet imply policy-owned trade eligibility" not in math_contract
    assert "paper fills or settlement truth" not in math_contract
    assert "policy, risk, and settlement placeholders" not in bootstrap_gaps


def test_realized_feedback_docs_no_longer_treat_research_loop_as_missing() -> None:
    blocker_doc = (REPO_ROOT / "docs" / "issues" / "paper_runtime_blockers.md").read_text()
    task_doc = (
        REPO_ROOT / "docs" / "task" / "global_regime_condition_and_shadow_stack.md"
    ).read_text()
    repo_map = (REPO_ROOT / ".ai" / "index" / "current_repo_map.md").read_text()

    assert "`research_loop/` is only partially governed" not in blocker_doc
    assert "RESEARCH-001" in blocker_doc
    assert "experiment_realized_feedback_v1" in task_doc
    assert "advisory realized-feedback comparison receipts" in task_doc
    assert "experiment_realized_feedback_v1" in repo_map
