# Graph Report - /home/netjer/Projects/AI-Frame/Brain/Defi-engine  (2026-04-19)

## Corpus Check
- 156 files · ~164,767 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 2058 nodes · 9434 edges · 176 communities detected
- Extraction: 18% EXTRACTED · 82% INFERRED · 0% AMBIGUOUS · INFERRED: 7725 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Settings` - 403 edges
2. `IngestRun` - 212 edges
3. `SourceHealthEvent` - 210 edges
4. `CaptureRunner` - 190 edges
5. `ConditionGlobalRegimeSnapshotV1` - 164 edges
6. `ConditionScorer` - 157 edges
7. `ShadowRunner` - 157 edges
8. `AdapterError` - 151 edges
9. `FeatureMaterializer` - 145 edges
10. `PaperPracticeRuntime` - 139 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Copy a table from SQLite canonical truth into DuckDB.          Args:`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/analytics/duckdb_mirror.py
- `Settings` --uses--> `Execute a read query against the DuckDB analytics mirror.          Args:`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/analytics/duckdb_mirror.py
- `Alembic environment configuration for D5 Trading Engine.` --uses--> `Base`  [INFERRED]
  sql/migrations/env.py → /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/storage/truth/models.py
- `Run migrations in 'offline' mode (SQL script generation).` --uses--> `Base`  [INFERRED]
  sql/migrations/env.py → /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/storage/truth/models.py
- `Run migrations in 'online' mode (direct database connection).` --uses--> `Base`  [INFERRED]
  sql/migrations/env.py → /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/storage/truth/models.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (159): capture(), D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic, Review one bounded advisory proposal and write review receipts., Run data capture for a specific provider or all., Run data capture for a specific provider or all., Compare reviewed proposals and optionally choose the next bounded experiment., D5 Trading Engine — crypto data capture + research engine., Show engine health — recent ingest runs and source health. (+151 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (119): Add the first explicit risk global regime gate table.  Revision ID: 006 Revises:, upgrade(), status(), sync_duckdb(), Copy a table from SQLite canonical truth into DuckDB.          Args:, Execute a read query against the DuckDB analytics mirror.          Args:, _build_alembic_config(), _ensure_dirs() (+111 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (159): Artifact writing plus canonical SQL receipts., Persist an artifact receipt in canonical SQL truth., Write a JSON artifact and record its SQL receipt., Write a text artifact and record its SQL receipt., record_artifact_reference(), _sha256(), write_json_artifact(), write_text_artifact() (+151 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (122): BacktestTruthOwner, Settlement-owned backtest replay ledger for spot-first truth., Spot-only backtest replay owner with explicit assumptions., DeclarativeBase, Alembic environment configuration for D5 Trading Engine., Run migrations in 'offline' mode (SQL script generation)., Run migrations in 'online' mode (direct database connection)., run_migrations_offline() (+114 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (106): ConfigError, D5Error, FeatureError, NormalizeError, D5 Trading Engine — Error Hierarchy  All custom exceptions inherit from D5Error, Base error for all D5 trading engine exceptions., Configuration-related errors (missing keys, bad values)., Errors during raw → canonical normalization. (+98 more)

### Community 5 - "Community 5"
Cohesion: 0.26
Nodes (139): CoinbaseClient, FredClient, HeliusClient, JupiterClient, MassiveClient, CaptureError, Errors during data capture orchestration., QuoteSnapshot (+131 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (48): ABC, BaseModel, predict(), Reusable base interface for D5 model adapters., Uniform adapter contract for reusable research models., Return default classification/regression metrics when ground truth exists., Return the standard artifact directory for this model family/version., Return feature-importance scores when the backend exposes them. (+40 more)

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (41): cli(), compare_proposals(), _emit_cli_result(), hydrate_history(), init(), main(), materialize_features(), paper_practice_status() (+33 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (51): main(), parse_args(), read_text(), accepted_receipts_dir(), atomic_write_json(), clear_processed_finder(), clear_stale_completion_trigger(), completion_writer_path() (+43 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (38): _document_batches(), download_data(), download_single_shard(), evaluate_bpb(), get_token_bytes(), list_parquet_files(), make_dataloader(), One-time data preparation for autoresearch experiments. Downloads data shards an (+30 more)

### Community 10 - "Community 10"
Cohesion: 0.1
Nodes (56): atomic_write_json(), atomic_write_text(), audit_ai_surfaces(), build_parser(), build_review_qmd(), classify_ai_file(), classify_dropbox_path(), compute_truth_context() (+48 more)

### Community 11 - "Community 11"
Cohesion: 0.13
Nodes (9): _iter_dates(), MassiveBackfillDayStatus, _parse_iso_date(), Bounded historical Massive minute-aggregate backfill orchestration., Resolve per-day actions for a bounded Massive history window., Group contiguous pending days into REST range chunks., Resolve the bounded two-year Massive crypto free-tier history window., Return bounded cache completeness for the fixed free-tier history window. (+1 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (13): fit_gaussian_hmm(), fit_gaussian_mixture_regime_proxy(), fit_hmm_or_gmm(), hmmlearn_available(), map_regime_state_semantics(), predict_regime_states(), Runtime-adjacent regime-model ownership for bounded condition scoring., Return True when the optional hmmlearn dependency is installed. (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.17
Nodes (12): filter_markov_regression(), fit_markov_regression(), markov_log_likelihood(), predict_markov_regime_states(), _probability_matrix(), Optional statsmodels-based shadow regime candidate., Return True when the optional statsmodels dependency is installed., Fit a bounded Markov-switching regression over one endogenous series. (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.53
Nodes (12): load_watch_module(), packet_summaries(), seed_receipts(), seed_repo(), test_ai_audit_classifies_delete_candidate_and_archives_ignored_outputs(), test_lock_prevents_second_invocation(), test_paper_cycle_packets_emit_once(), test_sandbox_context_points_to_copied_db_paths() (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.32
Nodes (11): dispatch(), ensure_rules_file(), event_file_from_obj(), load_lane_sessions(), load_state(), main(), next_events(), save_state() (+3 more)

### Community 16 - "Community 16"
Cohesion: 0.31
Nodes (7): _mark_proposal_reviewed(), _seed_reviewable_experiment_context(), _seed_strategy_experiment_context(), test_compare_proposals_choose_top_supersedes_same_kind_only(), test_compare_proposals_prefers_paper_over_earlier_stage_evidence(), test_proposal_review_rejects_runtime_widening_language(), test_proposal_review_writes_truth_receipts_and_accepts_bounded_evidence()

### Community 17 - "Community 17"
Cohesion: 0.33
Nodes (9): _make_training_fixture(), test_codex_dispatch_dry_run_uses_exec_json_and_repo_cd(), test_codex_dispatch_initializes_persistent_trader_lane_and_records_session(), test_codex_dispatch_resumes_existing_trader_lane(), test_event_watcher_materializes_missing_rules_from_example(), test_event_watcher_writes_trader_lane_status(), test_render_prompt_includes_harness_context_and_baseline(), test_resolve_training_context_uses_repo_doctrine_and_recent_artifacts() (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.24
Nodes (9): _build_frontmatter(), _normalize_frontmatter_value(), Template-backed QMD rendering., Normalize metadata into YAML-safe scalar/list/dict values., Render deterministic YAML frontmatter for QMD packets., Build the canonical small trading frontmatter payload for QMD evidence., Render a lightweight QMD report from the named template., render_qmd() (+1 more)

### Community 19 - "Community 19"
Cohesion: 0.44
Nodes (9): _event_payload(), _first_existing(), _latest_json(), _load_json(), main(), _relative_to_repo(), _resolve_repo_root(), resolve_training_context() (+1 more)

### Community 20 - "Community 20"
Cohesion: 0.25
Nodes (7): build_isolation_forest(), build_random_forest_classifier(), build_xgboost_classifier(), Runtime-adjacent deterministic model builders for paper-first research., Construct the bounded anomaly-veto model used by research lanes., Construct the deterministic Random Forest baseline., Construct the deterministic XGBoost baseline.

### Community 21 - "Community 21"
Cohesion: 0.32
Nodes (4): get_training_profile(), Paper-practice training regimens.  These profiles govern data budget, warmup, an, _serialize_profile(), summarize_training_profile_readiness()

### Community 22 - "Community 22"
Cohesion: 0.25
Nodes (0):

### Community 23 - "Community 23"
Cohesion: 0.48
Nodes (6): load_instrument_scope(), load_metrics_registry(), load_story_classes(), load_strategy_registry(), load_yaml_registry(), Machine-readable registries for bounded research configuration.

### Community 24 - "Community 24"
Cohesion: 0.48
Nodes (5): _seed_tracked_tokens(), test_backtest_truth_owner_opens_replays_and_closes_spot_session(), test_backtest_truth_owner_rejects_non_monotonic_fill_timestamps(), test_backtest_truth_owner_requires_marks_for_open_positions(), _tracked_mint()

### Community 25 - "Community 25"
Cohesion: 0.62
Nodes (6): _candidate_runner(), _prepare_regime_compare_history(), test_cli_run_shadow_regime_model_compare_fails_closed_on_short_history(), test_cli_run_shadow_regime_model_compare_handles_missing_statsmodels_dependency(), test_cli_run_shadow_regime_model_compare_persists_receipts_and_artifacts(), test_proposal_review_accepts_regime_model_compare_follow_on()

### Community 26 - "Community 26"
Cohesion: 0.53
Nodes (5): append_training_event(), append_training_event_safe(), build_training_event(), _normalize_relpaths(), Thin training-automation event helpers for watcher-driven Codex review.

### Community 27 - "Community 27"
Cohesion: 0.67
Nodes (5): bullets(), load_event(), main(), resolve_training_context(), script_repo_root()

### Community 28 - "Community 28"
Cohesion: 0.6
Nodes (5): _seed_research_repo_truth(), test_cli_compare_proposals_selects_reviewed_candidate(), test_cli_review_proposal_records_acceptance_receipts(), test_cli_run_label_program_scores_and_records_proposal(), test_cli_run_strategy_eval_writes_challenger_report()

### Community 29 - "Community 29"
Cohesion: 0.53
Nodes (4): _classification_frame(), test_isolation_forest_model_supports_scores_flags_and_save_load(), test_random_forest_model_train_predict_save_load(), test_xgboost_model_train_predict_save_load()

### Community 30 - "Community 30"
Cohesion: 0.33
Nodes (0):

### Community 31 - "Community 31"
Cohesion: 0.67
Nodes (5): _seed_condition_run(), test_cli_run_paper_cycle_creates_paper_truth_and_qmd(), test_cli_run_paper_cycle_fails_closed_without_strategy_report(), test_paper_trade_operator_close_cycle_writes_close_artifacts(), _write_strategy_report()

### Community 32 - "Community 32"
Cohesion: 0.4
Nodes (0):

### Community 33 - "Community 33"
Cohesion: 0.4
Nodes (0):

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (1): Add the first explicit backtest truth ledger tables.  Revision ID: 010 Revises:

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (1): Add the first bounded feature materialization table.  Revision ID: 003 Revises:

### Community 36 - "Community 36"
Cohesion: 0.5
Nodes (1): Add global regime inputs and condition scoring truth tables.  Revision ID: 004 R

### Community 37 - "Community 37"
Cohesion: 0.5
Nodes (1): Add the first explicit paper settlement ledger tables.  Revision ID: 007 Revises

### Community 38 - "Community 38"
Cohesion: 0.5
Nodes (1): Add proposal review truth.  Revision ID: 012 Revises: 011 Create Date: 2026-04-1

### Community 39 - "Community 39"
Cohesion: 0.5
Nodes (1): Add advisory realized-feedback comparison receipts for shadow experiments.  Revi

### Community 40 - "Community 40"
Cohesion: 0.5
Nodes (1): Add Coinbase derivative metadata columns to market instrument registry.  Revisio

### Community 41 - "Community 41"
Cohesion: 0.5
Nodes (1): Add artifact receipts and improvement proposal truth.  Revision ID: 011 Revises:

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (1): Add the first explicit execution-intent owner surface.  Revision ID: 009 Revises

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (1): Initial schema — 20 tables for D5 Trading Engine  Revision ID: 001 Revises: None

### Community 44 - "Community 44"
Cohesion: 0.5
Nodes (1): Add proposal comparison and supersession truth.  Revision ID: 013 Revises: 012 C

### Community 45 - "Community 45"
Cohesion: 0.5
Nodes (1): Add paper-practice profile, loop, and decision truth.  Revision ID: 014 Revises:

### Community 46 - "Community 46"
Cohesion: 0.5
Nodes (1): Source expansion slice for event-time aware quotes and new market tables.  Revis

### Community 47 - "Community 47"
Cohesion: 0.5
Nodes (1): Add the first explicit policy global regime trace table.  Revision ID: 005 Revis

### Community 48 - "Community 48"
Cohesion: 0.83
Nodes (3): _list_value(), _load_payload(), main()

### Community 49 - "Community 49"
Cohesion: 0.5
Nodes (0):

### Community 50 - "Community 50"
Cohesion: 0.83
Nodes (3): _seed_strategy_report(), _seed_walk_forward_history(), test_backtest_walk_forward_replays_windows_and_governor_gates_profile_adaptation()

### Community 51 - "Community 51"
Cohesion: 0.67
Nodes (0):

### Community 52 - "Community 52"
Cohesion: 0.67
Nodes (0):

### Community 53 - "Community 53"
Cohesion: 0.67
Nodes (0):

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Shadow-only model registry.  These entries are visible to research and reporting

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (0):

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (0):

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (0):

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (0):

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Train or initialize the model and return metadata.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Generate model predictions.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Persist model artifacts to disk.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): Load model artifacts from disk.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Return True when CUDA tooling appears to be available.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Helius WebSocket URL (constructed from API key).

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Helius enhanced API base URL.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Describe which Coinbase credential shape is configured.

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): Describe which Coinbase credential shape is configured.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Massive REST API base URL.

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): SQLAlchemy database URL.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Parquet data directory.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Helius WebSocket URL (constructed from API key).

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Helius enhanced API base URL.

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): Describe which Coinbase credential shape is configured.

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): Massive REST API base URL.

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): SQLAlchemy database URL.

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Parquet data directory.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Massive REST API base URL.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): Build the canonical small trading frontmatter payload for QMD evidence.

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): Render a lightweight QMD report from the named template.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Helius WebSocket URL (constructed from API key).

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): Helius enhanced API base URL.

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 116 - "Community 116"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 117 - "Community 117"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 118 - "Community 118"
Cohesion: 1.0
Nodes (1): Normalized OHLCV bars from exchange-style providers.

### Community 119 - "Community 119"
Cohesion: 1.0
Nodes (1): Normalized trade prints from exchange-style providers.

### Community 120 - "Community 120"
Cohesion: 1.0
Nodes (1): Normalized L2 book snapshots or updates from exchange-style providers.

### Community 121 - "Community 121"
Cohesion: 1.0
Nodes (1): Feature pipeline tracking.

### Community 122 - "Community 122"
Cohesion: 1.0
Nodes (1): First bounded feature table for spot, chain, and macro minute context.

### Community 123 - "Community 123"
Cohesion: 1.0
Nodes (1): Market-wide 15-minute regime inputs derived from canonical truth.

### Community 124 - "Community 124"
Cohesion: 1.0
Nodes (1): Track condition scoring runs and the model semantics they produced.

### Community 125 - "Community 125"
Cohesion: 1.0
Nodes (1): Latest scored regime snapshot for a closed 15-minute bucket.

### Community 126 - "Community 126"
Cohesion: 1.0
Nodes (1): Policy-owned trace for bounded global regime eligibility decisions.

### Community 127 - "Community 127"
Cohesion: 1.0
Nodes (1): Risk-owned veto receipt over persisted global regime policy truth.

### Community 128 - "Community 128"
Cohesion: 1.0
Nodes (1): Settlement-owned paper session lifecycle receipt.

### Community 129 - "Community 129"
Cohesion: 1.0
Nodes (1): Settlement-owned paper session lifecycle receipt.

### Community 130 - "Community 130"
Cohesion: 1.0
Nodes (1): Append-only paper fill receipt tied to explicit upstream provenance.

### Community 131 - "Community 131"
Cohesion: 1.0
Nodes (1): Current paper position state for one mint inside one paper session.

### Community 132 - "Community 132"
Cohesion: 1.0
Nodes (1): Settlement-owned report derived from paper sessions, fills, and positions.

### Community 133 - "Community 133"
Cohesion: 1.0
Nodes (1): Settlement-owned backtest replay session with explicit assumptions.

### Community 134 - "Community 134"
Cohesion: 1.0
Nodes (1): Append-only backtest fill receipt with explicit replay assumptions.

### Community 135 - "Community 135"
Cohesion: 1.0
Nodes (1): Current backtest position state for one mint inside one replay session.

### Community 136 - "Community 136"
Cohesion: 1.0
Nodes (1): Settlement-owned report derived from backtest sessions and replay fills.

### Community 137 - "Community 137"
Cohesion: 1.0
Nodes (1): Research experiment tracking.

### Community 138 - "Community 138"
Cohesion: 1.0
Nodes (1): Experiment metric values.

### Community 139 - "Community 139"
Cohesion: 1.0
Nodes (1): Research-owned advisory comparison between shadow context and paper outcomes.

### Community 140 - "Community 140"
Cohesion: 1.0
Nodes (1): Canonical SQL receipt for evidence artifacts written to disk.

### Community 141 - "Community 141"
Cohesion: 1.0
Nodes (1): Reviewable bounded-improvement proposal with no runtime authority.

### Community 142 - "Community 142"
Cohesion: 1.0
Nodes (1): Deterministic review receipt over a bounded advisory proposal.

### Community 143 - "Community 143"
Cohesion: 1.0
Nodes (1): Comparison run over reviewed proposals.

### Community 144 - "Community 144"
Cohesion: 1.0
Nodes (1): One ranked proposal candidate inside a comparison run.

### Community 145 - "Community 145"
Cohesion: 1.0
Nodes (1): Append-only supersession edge between selected and displaced proposals.

### Community 146 - "Community 146"
Cohesion: 1.0
Nodes (1): Render a lightweight QMD report from the named template.

### Community 147 - "Community 147"
Cohesion: 1.0
Nodes (1): Fit the preferred regime model, falling back to GMM when hmmlearn is absent.

### Community 148 - "Community 148"
Cohesion: 1.0
Nodes (1): Predict latent regime states and per-row probabilities.

### Community 149 - "Community 149"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 150 - "Community 150"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 151 - "Community 151"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 152 - "Community 152"
Cohesion: 1.0
Nodes (1): SQLAlchemy database URL.

### Community 153 - "Community 153"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 154 - "Community 154"
Cohesion: 1.0
Nodes (1): Parquet data directory.

### Community 155 - "Community 155"
Cohesion: 1.0
Nodes (1): Helius WebSocket URL (constructed from API key).

### Community 156 - "Community 156"
Cohesion: 1.0
Nodes (1): Helius enhanced API base URL.

### Community 157 - "Community 157"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 158 - "Community 158"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 159 - "Community 159"
Cohesion: 1.0
Nodes (1): Massive REST API base URL.

### Community 160 - "Community 160"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 161 - "Community 161"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 162 - "Community 162"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 163 - "Community 163"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 164 - "Community 164"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 165 - "Community 165"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 166 - "Community 166"
Cohesion: 1.0
Nodes (1): SQLAlchemy database URL.

### Community 167 - "Community 167"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 168 - "Community 168"
Cohesion: 1.0
Nodes (1): Parquet data directory.

### Community 169 - "Community 169"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 170 - "Community 170"
Cohesion: 1.0
Nodes (1): Append-only paper fill receipt tied to explicit upstream provenance.

### Community 171 - "Community 171"
Cohesion: 1.0
Nodes (1): Current paper position state for one mint inside one paper session.

### Community 172 - "Community 172"
Cohesion: 1.0
Nodes (1): Settlement-owned report derived from paper sessions, fills, and positions.

### Community 173 - "Community 173"
Cohesion: 1.0
Nodes (1): Research experiment tracking.

### Community 174 - "Community 174"
Cohesion: 1.0
Nodes (1): Experiment metric values.

### Community 175 - "Community 175"
Cohesion: 1.0
Nodes (1): Research-owned advisory comparison between shadow context and paper outcomes.

## Knowledge Gaps
- **268 isolated node(s):** `Add the first explicit backtest truth ledger tables.  Revision ID: 010 Revises:`, `Add the first bounded feature materialization table.  Revision ID: 003 Revises:`, `Add global regime inputs and condition scoring truth tables.  Revision ID: 004 R`, `Add the first explicit paper settlement ledger tables.  Revision ID: 007 Revises`, `Add proposal review truth.  Revision ID: 012 Revises: 011 Create Date: 2026-04-1` (+263 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 54`** (2 nodes): `shadow_only.py`, `Shadow-only model registry.  These entries are visible to research and reporting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (2 nodes): `emit_event.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (2 nodes): `test_reporting_qmd.py`, `test_render_qmd_includes_trading_frontmatter_metadata()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (2 nodes): `test_live_regime_cycle.py`, `test_live_regime_cycle_writes_paper_ready_receipt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (2 nodes): `test_reporting_artifacts.py`, `test_reporting_artifacts_write_sql_receipts()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Train or initialize the model and return metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Generate model predictions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Persist model artifacts to disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `Load model artifacts from disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Return True when CUDA tooling appears to be available.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Helius WebSocket URL (constructed from API key).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Helius enhanced API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Describe which Coinbase credential shape is configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `Describe which Coinbase credential shape is configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Massive REST API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `SQLAlchemy database URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Parquet data directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Helius WebSocket URL (constructed from API key).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Helius enhanced API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `Describe which Coinbase credential shape is configured.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `Massive REST API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `SQLAlchemy database URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Parquet data directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Massive REST API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `Build the canonical small trading frontmatter payload for QMD evidence.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `Render a lightweight QMD report from the named template.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Helius WebSocket URL (constructed from API key).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `Helius enhanced API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 116`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 117`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 118`** (1 nodes): `Normalized OHLCV bars from exchange-style providers.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 119`** (1 nodes): `Normalized trade prints from exchange-style providers.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 120`** (1 nodes): `Normalized L2 book snapshots or updates from exchange-style providers.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 121`** (1 nodes): `Feature pipeline tracking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 122`** (1 nodes): `First bounded feature table for spot, chain, and macro minute context.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 123`** (1 nodes): `Market-wide 15-minute regime inputs derived from canonical truth.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 124`** (1 nodes): `Track condition scoring runs and the model semantics they produced.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 125`** (1 nodes): `Latest scored regime snapshot for a closed 15-minute bucket.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 126`** (1 nodes): `Policy-owned trace for bounded global regime eligibility decisions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 127`** (1 nodes): `Risk-owned veto receipt over persisted global regime policy truth.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 128`** (1 nodes): `Settlement-owned paper session lifecycle receipt.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 129`** (1 nodes): `Settlement-owned paper session lifecycle receipt.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 130`** (1 nodes): `Append-only paper fill receipt tied to explicit upstream provenance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 131`** (1 nodes): `Current paper position state for one mint inside one paper session.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 132`** (1 nodes): `Settlement-owned report derived from paper sessions, fills, and positions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 133`** (1 nodes): `Settlement-owned backtest replay session with explicit assumptions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 134`** (1 nodes): `Append-only backtest fill receipt with explicit replay assumptions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 135`** (1 nodes): `Current backtest position state for one mint inside one replay session.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 136`** (1 nodes): `Settlement-owned report derived from backtest sessions and replay fills.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 137`** (1 nodes): `Research experiment tracking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 138`** (1 nodes): `Experiment metric values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 139`** (1 nodes): `Research-owned advisory comparison between shadow context and paper outcomes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 140`** (1 nodes): `Canonical SQL receipt for evidence artifacts written to disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 141`** (1 nodes): `Reviewable bounded-improvement proposal with no runtime authority.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 142`** (1 nodes): `Deterministic review receipt over a bounded advisory proposal.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 143`** (1 nodes): `Comparison run over reviewed proposals.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 144`** (1 nodes): `One ranked proposal candidate inside a comparison run.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 145`** (1 nodes): `Append-only supersession edge between selected and displaced proposals.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 146`** (1 nodes): `Render a lightweight QMD report from the named template.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 147`** (1 nodes): `Fit the preferred regime model, falling back to GMM when hmmlearn is absent.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 148`** (1 nodes): `Predict latent regime states and per-row probabilities.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 149`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 150`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 151`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 152`** (1 nodes): `SQLAlchemy database URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 153`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 154`** (1 nodes): `Parquet data directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 155`** (1 nodes): `Helius WebSocket URL (constructed from API key).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 156`** (1 nodes): `Helius enhanced API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 157`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 158`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 159`** (1 nodes): `Massive REST API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 160`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 161`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 162`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 163`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 164`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 165`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 166`** (1 nodes): `SQLAlchemy database URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 167`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 168`** (1 nodes): `Parquet data directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 169`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 170`** (1 nodes): `Append-only paper fill receipt tied to explicit upstream provenance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 171`** (1 nodes): `Current paper position state for one mint inside one paper session.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 172`** (1 nodes): `Settlement-owned report derived from paper sessions, fills, and positions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 173`** (1 nodes): `Research experiment tracking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 174`** (1 nodes): `Experiment metric values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 175`** (1 nodes): `Research-owned advisory comparison between shadow context and paper outcomes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 7`, `Community 11`, `Community 26`?**
  _High betweenness centrality (0.267) - this node is a cross-community bridge._
- **Why does `read_text()` connect `Community 8` to `Community 2`, `Community 3`, `Community 7`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._
- **Why does `Trajectory — advisory forecasting and scenario generation (scaffold).` connect `Community 3` to `Community 1`, `Community 6`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 400 inferred relationships involving `Settings` (e.g. with `get_settings()` and `FredNormalizer`) actually correct?**
  _`Settings` has 400 INFERRED edges - model-reasoned connections that need verification._
- **Are the 209 inferred relationships involving `IngestRun` (e.g. with `D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic` and `Render one CLI result in either machine or human form.`) actually correct?**
  _`IngestRun` has 209 INFERRED edges - model-reasoned connections that need verification._
- **Are the 207 inferred relationships involving `SourceHealthEvent` (e.g. with `D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic` and `Render one CLI result in either machine or human form.`) actually correct?**
  _`SourceHealthEvent` has 207 INFERRED edges - model-reasoned connections that need verification._
- **Are the 161 inferred relationships involving `CaptureRunner` (e.g. with `D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic` and `Render one CLI result in either machine or human form.`) actually correct?**
  _`CaptureRunner` has 161 INFERRED edges - model-reasoned connections that need verification._