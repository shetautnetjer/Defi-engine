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
    REPO_ROOT / "docs" / "plans" / "autonomous_paper_practice_loop.md",
    REPO_ROOT / "docs" / "task" / "bootstrap_truth_sync.md",
    REPO_ROOT / "docs" / "task" / "trading_qmd_report_contract.md",
    REPO_ROOT / "docs" / "architecture" / "bootstrap_architecture.md",
    REPO_ROOT / "docs" / "architecture" / "backtest_truth_contract.md",
    REPO_ROOT / "docs" / "runbooks" / "first_capture.md",
    REPO_ROOT / "docs" / "runbooks" / "feature_condition_shadow_cycle.md",
    REPO_ROOT / "docs" / "runbooks" / "ralph_tmux_swarm.md",
    REPO_ROOT / "docs" / "math" / "regime_shadow_modeling_contracts.md",
    REPO_ROOT / "docs" / "math" / "market_regime_forecast_and_labeling_program.md",
    REPO_ROOT / "docs" / "math" / "strategy_family_registry.md",
    REPO_ROOT / "docs" / "policy" / "runtime_authority_and_promotion_ladder.md",
    REPO_ROOT / "docs" / "policy" / "writer_story_promotion_rubric.md",
    REPO_ROOT / "docs" / "test" / "bootstrap_validation.md",
]
TRAINING_WORKSPACE_DOCS = [
    REPO_ROOT / "training" / "README.md",
    REPO_ROOT / "training" / "AGENTS.md",
    REPO_ROOT / "training" / "trading_agent_harness.md",
    REPO_ROOT / "training" / "program.md",
    REPO_ROOT / "training" / "vendor" / "autoresearch" / "UPSTREAM.md",
    REPO_ROOT / "training" / "automation" / "README.md",
    REPO_ROOT / "training" / "config" / "source_sets.example.json",
    REPO_ROOT / "training" / "rubrics" / "paper_practice_default.json",
    REPO_ROOT / "training" / "rubrics" / "training_regime_rubric.md",
    REPO_ROOT / "training" / "prompts" / "training_review.md.tmpl",
    REPO_ROOT / "training" / "bin" / "emit_training_event.py",
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
    REPO_ROOT / "docs" / "handoff" / "README.md",
    REPO_ROOT / "docs" / "handoff" / "2026-04-12_bootstrap_phase_1.md",
]


def test_single_root_env_template_exists() -> None:
    assert (REPO_ROOT / ".env.example").exists()
    assert not (REPO_ROOT / "env.example").exists()


def test_required_bootstrap_docs_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not path.exists()]
    assert not missing


def test_training_workspace_docs_exist() -> None:
    missing = [path for path in TRAINING_WORKSPACE_DOCS if not path.exists()]
    assert not missing


def test_training_workspace_grounding_docs_link_notion_and_local_doctrine() -> None:
    training_agents = (REPO_ROOT / "training" / "AGENTS.md").read_text()
    training_readme = (REPO_ROOT / "training" / "README.md").read_text()
    training_harness = (REPO_ROOT / "training" / "trading_agent_harness.md").read_text()
    training_program = (REPO_ROOT / "training" / "program.md").read_text()
    training_rubric = (
        REPO_ROOT / "training" / "rubrics" / "training_regime_rubric.md"
    ).read_text()

    notion_url = "https://www.notion.so/Training-regime-347936b02c25803d8ec4cb77cf4040d6?source=copy_link"

    assert notion_url in training_agents
    assert "Repo-owned files in `training/` remain the durable" in training_agents
    assert "`training/trading_agent_harness.md`" in training_agents
    assert notion_url in training_readme
    assert "The Notion page is stronger on rubric and autoresearch program framing." in training_readme
    assert "`training/trading_agent_harness.md`" in training_readme
    assert "`training/program.md`" in training_readme
    assert "`training/rubrics/training_regime_rubric.md`" in training_readme
    assert "`docs/task/trading_qmd_report_contract.md`" in training_readme
    assert "Trading Agent Harness" in training_harness
    assert "Required Read Order" in training_harness
    assert "keep, revert, or shadow" in training_harness
    assert "paper-only" in training_harness
    assert "trading_qmd_report_contract.md" in training_harness
    assert "repo-owned operating contract" in training_program
    assert "best evidence-driven trading system" in training_program
    assert "Allowed Surfaces" in training_program
    assert "Training Regime Rubric" in training_rubric
    assert "Failure Attribution Matrix" in training_rubric


def test_agents_files_include_superpowers_routing() -> None:
    root_agents = (REPO_ROOT / "AGENTS.md").read_text()
    training_agents = (REPO_ROOT / "training" / "AGENTS.md").read_text()

    for contents in (root_agents, training_agents):
        assert "Superpowers Routing" in contents
        assert "superpowers:writing-plans" in contents
        assert "superpowers:executing-plans" in contents
        assert "superpowers:systematic-debugging" in contents
        assert "superpowers:verification-before-completion" in contents


def test_readme_and_runbooks_reference_flatfile_warehouse_and_qmd_contract() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    current_truth = (REPO_ROOT / "docs" / "project" / "current_runtime_truth.md").read_text()
    first_capture = (REPO_ROOT / "docs" / "runbooks" / "first_capture.md").read_text()
    qmd_contract = (REPO_ROOT / "docs" / "task" / "trading_qmd_report_contract.md").read_text()
    training_automation = (REPO_ROOT / "training" / "automation" / "README.md").read_text()

    assert "data/parquet/" in readme
    assert "docs/task/trading_qmd_report_contract.md" in readme
    assert "codex exec --json -C <repo>" in readme
    assert "Parquet" in current_truth
    assert "falls back to REST minute aggregates" in current_truth
    assert "Storage contract:" in first_capture
    assert "raw JSONL and CSV.gz source artifacts" in first_capture
    assert "data/parquet/" in first_capture
    assert "Flat Files Quickstart" in qmd_contract
    assert "https://massive.com/docs/flat-files/quickstart" in qmd_contract
    assert "https://developers.openai.com/codex/changelog" in qmd_contract
    assert "`AGENTS.md`" in training_automation
    assert "exec-server" in training_automation


def test_navigation_agents_exist_only_in_high_value_runtime_roots() -> None:
    expected = [
        REPO_ROOT / "src" / "d5_trading_engine" / "AGENTS.md",
        REPO_ROOT / "src" / "d5_trading_engine" / "storage" / "AGENTS.md",
        REPO_ROOT / "src" / "d5_trading_engine" / "research_loop" / "AGENTS.md",
        REPO_ROOT / "src" / "d5_trading_engine" / "models" / "AGENTS.md",
    ]
    for path in expected:
        assert path.exists(), f"missing navigation AGENTS file: {path}"

    assert not (REPO_ROOT / "docs" / "AGENTS.md").exists()
    assert not (REPO_ROOT / ".ai" / "AGENTS.md").exists()


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


def test_docs_do_not_reference_removed_autopromotion_flow() -> None:
    stale_strings = [
        "story_autopromotion",
        "story_autopromotion_receipt.json",
        "--auto-promote",
    ]
    doc_roots = [REPO_ROOT / "docs", REPO_ROOT / "AGENTS.md"]

    for root in doc_roots:
        paths = [root] if root.is_file() else list(root.rglob("*.md"))
        for path in paths:
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
    assert "start_watch_adapter.sh" in runbook
    assert "status_watch_adapter.sh" in runbook
    assert "advisory-only" in runbook


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
    strategy_registry = (
        REPO_ROOT / "docs" / "math" / "strategy_family_registry.md"
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
    assert "trend_continuation_long_v1" in strategy_registry
    assert "RandomForestClassifier" in strategy_registry
    assert "XGBClassifier" in strategy_registry
    assert "advisory" in authority
    assert "writer-integrator" in authority
    assert "bounded research proposal review" in authority
    assert "docs/issues/" in writer_rubric
    assert "docs/gaps/" in writer_rubric
    assert "best next governed slice" in writer_rubric
    assert "label_program" in writer_rubric
    assert "strategy_eval" in writer_rubric
    assert "terminal_complete" in completion


def test_current_runtime_truth_and_ai_packet_reference_machine_readable_swarm_law() -> None:
    runtime_truth = (REPO_ROOT / "docs" / "project" / "current_runtime_truth.md").read_text()
    ai_readme = (REPO_ROOT / ".ai" / "README.md").read_text()
    dropbox_readme = (REPO_ROOT / ".ai" / "dropbox" / "README.md").read_text()
    repo_map = (REPO_ROOT / ".ai" / "index" / "current_repo_map.md").read_text()
    backtest_arch = (
        REPO_ROOT / "docs" / "architecture" / "backtest_truth_contract.md"
    ).read_text()

    assert "execution intent" in runtime_truth.lower()
    assert "backtest" in runtime_truth.lower()
    assert "research_proposal_review_receipt.json" in runtime_truth
    assert "research_proposal_priority_receipt.json" in runtime_truth
    assert "regime-model-compare-v1" in runtime_truth
    assert "run-paper-practice-loop" in runtime_truth
    assert "paper_practice_profile_v1" in runtime_truth
    assert "watcher" in runtime_truth.lower()
    assert "Stage 1" in runtime_truth
    assert "current truth consolidation" in runtime_truth
    assert ".ai/swarm/" in ai_readme
    assert "policy-only" in ai_readme
    assert "story_classes.yaml" in ai_readme
    assert "watcher.yaml" in ai_readme
    assert "watcher.md" in ai_readme
    assert "start_watch_adapter.sh" in ai_readme
    assert "proposal_comparison_v1" in ai_readme
    assert "proposal_supersession_v1" in ai_readme
    assert "research_proposal_priority_receipt.json" in ai_readme
    assert "regime-model-compare-v1" in ai_readme
    assert "regime_model_compare_follow_on" in ai_readme
    assert "docs/handoff/" in ai_readme
    assert "prd.json" in ai_readme
    assert "progress.txt" in ai_readme
    assert "watcher_state.json" in dropbox_readme
    assert "watcher_latest.json" in dropbox_readme
    assert "watcher.lock" in dropbox_readme
    assert "research_proposal_review_receipt.json" in dropbox_readme
    assert "research_proposal_priority_receipt.json" in dropbox_readme
    assert "data/archive/ai_dropbox/" in dropbox_readme
    assert "docs/handoff/" in dropbox_readme
    assert ".ai/swarm/swarm.yaml" in repo_map
    assert "label_program_v1" in repo_map
    assert "strategy_eval_v1" in repo_map
    assert "proposal_comparison_v1" in repo_map
    assert "proposal_supersession_v1" in repo_map
    assert "research_proposal_priority_receipt.json" in repo_map
    assert "regime_model_compare_v1" in repo_map
    assert "regime_model_compare_follow_on" in repo_map
    assert "BacktestTruthOwner" in backtest_arch
    assert "spot-first" in backtest_arch


def test_docs_and_agents_route_handoff_vs_dropbox_cleanly() -> None:
    root_agents = (REPO_ROOT / "AGENTS.md").read_text()
    docs_index = (REPO_ROOT / "docs" / "README.md").read_text()
    handoff_readme = (REPO_ROOT / "docs" / "handoff" / "README.md").read_text()

    assert ".ai/dropbox/" in root_agents
    assert "docs/handoff/" in root_agents
    assert "prd.json" in root_agents
    assert "progress.txt" in root_agents
    assert ".ai/dropbox/" in docs_index
    assert "docs/handoff/" in docs_index
    assert "verbose human" in docs_index
    assert ".ai/dropbox/" in handoff_readme
    assert "durable human-readable continuation surface" in handoff_readme


def test_training_workspace_and_readme_expose_repo_owned_training_lane() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    training_readme = (REPO_ROOT / "training" / "README.md").read_text()
    training_agents = (REPO_ROOT / "training" / "AGENTS.md").read_text()
    upstream = (REPO_ROOT / "training" / "vendor" / "autoresearch" / "UPSTREAM.md").read_text()

    assert "d5 training bootstrap" in readme
    assert "d5 training walk-forward" in readme
    assert "d5 training review" in readme
    assert "d5 training loop" in readme
    assert "d5 training status" in readme
    assert "codex --exec" in training_readme
    assert "SQL as canonical truth" in training_readme
    assert "QMD as evidence" in training_readme
    assert "paper-only" in training_agents
    assert "one bounded thing at a time" in training_agents
    assert "karpathy/autoresearch" in upstream


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
