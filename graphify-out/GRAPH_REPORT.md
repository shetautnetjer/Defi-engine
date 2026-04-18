# Graph Report - /home/netjer/Projects/AI-Frame/Brain/Defi-engine  (2026-04-17)

## Corpus Check
- 127 files · ~110,842 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1391 nodes · 5506 edges · 86 communities detected
- Extraction: 23% EXTRACTED · 77% INFERRED · 0% AMBIGUOUS · INFERRED: 4249 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `Settings` - 268 edges
2. `IngestRun` - 106 edges
3. `SourceHealthEvent` - 104 edges
4. `ShadowRunner` - 99 edges
5. `CaptureRunner` - 96 edges
6. `ConditionGlobalRegimeSnapshotV1` - 88 edges
7. `get_session()` - 82 edges
8. `ConditionScorer` - 81 edges
9. `Base` - 76 edges
10. `ConditionScoringRun` - 76 edges

## Surprising Connections (you probably didn't know these)
- `Settings` --uses--> `Get or create the partition directory for a provider.          Args:`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/raw_store.py
- `Settings` --uses--> `Write records to a JSONL file atomically.          Each record is wrapped in a m`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/raw_store.py
- `Settings` --uses--> `Write a single payload record.          Convenience wrapper around write_jsonl f`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/raw_store.py
- `Settings` --uses--> `DuckDB analytics mirror for research queries.      Reads from:     - SQLite cano`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/analytics/duckdb_mirror.py
- `Settings` --uses--> `Copy a table from SQLite canonical truth into DuckDB.          Args:`  [INFERRED]
  /home/netjer/Projects/AI-Frame/Brain/Defi-engine/src/d5_trading_engine/config/settings.py → src/d5_trading_engine/storage/analytics/duckdb_mirror.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (110): materialize_features(), status(), sync_duckdb(), Copy a table from SQLite canonical truth into DuckDB.          Args:, Execute a read query against the DuckDB analytics mirror.          Args:, _build_alembic_config(), _ensure_dirs(), get_session() (+102 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (134): BacktestTruthOwner, Settlement-owned backtest replay ledger for spot-first truth., Spot-only backtest replay owner with explicit assumptions., DeclarativeBase, D5 Trading Engine — SQLAlchemy Engine Factory  Manages the canonical truth datab, Create runtime data directories if they don't exist., Set SQLite performance pragmas on connect., Create a new Coinbase raw DB session. (+126 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (108): Artifact writing plus canonical SQL receipts., Persist an artifact receipt in canonical SQL truth., Write a JSON artifact and record its SQL receipt., Write a text artifact and record its SQL receipt., record_artifact_reference(), _sha256(), write_json_artifact(), write_text_artifact() (+100 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (113): BaseModel, capture(), cli(), compare_proposals(), init(), main(), D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic, Run data capture for a specific provider or all. (+105 more)

### Community 4 - "Community 4"
Cohesion: 0.27
Nodes (91): CoinbaseClient, FredClient, HeliusClient, JupiterClient, MassiveClient, CaptureError, Errors during data capture orchestration., Raw Jupiter quote API responses. (+83 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (22): run_shadow(), ExperimentMetric, ExperimentRun, FeatureSpotChainMacroMinuteV1, Research experiment tracking., Experiment metric values., First bounded feature table for spot, chain, and macro minute context., RealizedFeedbackComparator (+14 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (29): ABC, BaseModel, predict(), Reusable base interface for D5 model adapters., Uniform adapter contract for reusable research models., Return default classification/regression metrics when ground truth exists., Return the standard artifact directory for this model family/version., Return feature-importance scores when the backend exposes them. (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (51): main(), parse_args(), read_text(), accepted_receipts_dir(), atomic_write_json(), clear_processed_finder(), clear_stale_completion_trigger(), completion_writer_path() (+43 more)

### Community 8 - "Community 8"
Cohesion: 0.1
Nodes (56): atomic_write_json(), atomic_write_text(), audit_ai_surfaces(), build_parser(), build_review_qmd(), classify_ai_file(), classify_dropbox_path(), compute_truth_context() (+48 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (16): create_all_for_tests_only(), get_engine(), initialize(), Create tables directly from ORM metadata for dev/test-only bootstrap., Get or create the Coinbase raw SQLite engine., Get or create the SQLAlchemy engine., Ensure the Coinbase raw DB exists with its raw tables., get_settings() (+8 more)

### Community 10 - "Community 10"
Cohesion: 0.18
Nodes (13): fit_gaussian_hmm(), fit_gaussian_mixture_regime_proxy(), fit_hmm_or_gmm(), hmmlearn_available(), map_regime_state_semantics(), predict_regime_states(), Runtime-adjacent regime-model ownership for bounded condition scoring., Return True when the optional hmmlearn dependency is installed. (+5 more)

### Community 11 - "Community 11"
Cohesion: 0.17
Nodes (12): filter_markov_regression(), fit_markov_regression(), markov_log_likelihood(), predict_markov_regime_states(), _probability_matrix(), Optional statsmodels-based shadow regime candidate., Return True when the optional statsmodels dependency is installed., Fit a bounded Markov-switching regression over one endogenous series. (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.53
Nodes (12): load_watch_module(), packet_summaries(), seed_receipts(), seed_repo(), test_ai_audit_classifies_delete_candidate_and_archives_ignored_outputs(), test_lock_prevents_second_invocation(), test_paper_cycle_packets_emit_once(), test_sandbox_context_points_to_copied_db_paths() (+4 more)

### Community 13 - "Community 13"
Cohesion: 0.24
Nodes (10): ConfigError, D5Error, NormalizeError, D5 Trading Engine — Error Hierarchy  All custom exceptions inherit from D5Error, Base error for all D5 trading engine exceptions., Configuration-related errors (missing keys, bad values)., Errors during raw → canonical normalization., Errors in storage layer (DB, file I/O). (+2 more)

### Community 14 - "Community 14"
Cohesion: 0.42
Nodes (7): _mark_proposal_reviewed(), _seed_reviewable_experiment_context(), _seed_strategy_experiment_context(), test_compare_proposals_choose_top_supersedes_same_kind_only(), test_compare_proposals_prefers_paper_over_earlier_stage_evidence(), test_proposal_review_rejects_runtime_widening_language(), test_proposal_review_writes_truth_receipts_and_accepts_bounded_evidence()

### Community 15 - "Community 15"
Cohesion: 0.25
Nodes (7): build_isolation_forest(), build_random_forest_classifier(), build_xgboost_classifier(), Runtime-adjacent deterministic model builders for paper-first research., Construct the bounded anomaly-veto model used by research lanes., Construct the deterministic Random Forest baseline., Construct the deterministic XGBoost baseline.

### Community 16 - "Community 16"
Cohesion: 0.48
Nodes (6): load_instrument_scope(), load_metrics_registry(), load_story_classes(), load_strategy_registry(), load_yaml_registry(), Machine-readable registries for bounded research configuration.

### Community 17 - "Community 17"
Cohesion: 0.48
Nodes (5): _seed_tracked_tokens(), test_backtest_truth_owner_opens_replays_and_closes_spot_session(), test_backtest_truth_owner_rejects_non_monotonic_fill_timestamps(), test_backtest_truth_owner_requires_marks_for_open_positions(), _tracked_mint()

### Community 18 - "Community 18"
Cohesion: 0.62
Nodes (6): _candidate_runner(), _prepare_regime_compare_history(), test_cli_run_shadow_regime_model_compare_fails_closed_on_short_history(), test_cli_run_shadow_regime_model_compare_handles_missing_statsmodels_dependency(), test_cli_run_shadow_regime_model_compare_persists_receipts_and_artifacts(), test_proposal_review_accepts_regime_model_compare_follow_on()

### Community 19 - "Community 19"
Cohesion: 0.6
Nodes (5): _seed_research_repo_truth(), test_cli_compare_proposals_selects_reviewed_candidate(), test_cli_review_proposal_records_acceptance_receipts(), test_cli_run_label_program_scores_and_records_proposal(), test_cli_run_strategy_eval_writes_challenger_report()

### Community 20 - "Community 20"
Cohesion: 0.53
Nodes (4): _classification_frame(), test_isolation_forest_model_supports_scores_flags_and_save_load(), test_random_forest_model_train_predict_save_load(), test_xgboost_model_train_predict_save_load()

### Community 21 - "Community 21"
Cohesion: 0.7
Nodes (4): _seed_condition_run(), test_cli_run_paper_cycle_creates_paper_truth_and_qmd(), test_cli_run_paper_cycle_fails_closed_without_strategy_report(), _write_strategy_report()

### Community 22 - "Community 22"
Cohesion: 0.5
Nodes (1): Add the first explicit backtest truth ledger tables.  Revision ID: 010 Revises:

### Community 23 - "Community 23"
Cohesion: 0.5
Nodes (1): Add the first bounded feature materialization table.  Revision ID: 003 Revises:

### Community 24 - "Community 24"
Cohesion: 0.5
Nodes (1): Add global regime inputs and condition scoring truth tables.  Revision ID: 004 R

### Community 25 - "Community 25"
Cohesion: 0.5
Nodes (1): Add the first explicit paper settlement ledger tables.  Revision ID: 007 Revises

### Community 26 - "Community 26"
Cohesion: 0.5
Nodes (1): Add proposal review truth.  Revision ID: 012 Revises: 011 Create Date: 2026-04-1

### Community 27 - "Community 27"
Cohesion: 0.5
Nodes (1): Add advisory realized-feedback comparison receipts for shadow experiments.  Revi

### Community 28 - "Community 28"
Cohesion: 0.5
Nodes (1): Add artifact receipts and improvement proposal truth.  Revision ID: 011 Revises:

### Community 29 - "Community 29"
Cohesion: 0.5
Nodes (1): Add the first explicit execution-intent owner surface.  Revision ID: 009 Revises

### Community 30 - "Community 30"
Cohesion: 0.5
Nodes (1): Initial schema — 20 tables for D5 Trading Engine  Revision ID: 001 Revises: None

### Community 31 - "Community 31"
Cohesion: 0.5
Nodes (1): Add proposal comparison and supersession truth.  Revision ID: 013 Revises: 012 C

### Community 32 - "Community 32"
Cohesion: 0.5
Nodes (1): Source expansion slice for event-time aware quotes and new market tables.  Revis

### Community 33 - "Community 33"
Cohesion: 0.5
Nodes (1): Add the first explicit policy global regime trace table.  Revision ID: 005 Revis

### Community 34 - "Community 34"
Cohesion: 0.5
Nodes (2): Add the first explicit risk global regime gate table.  Revision ID: 006 Revises:, upgrade()

### Community 35 - "Community 35"
Cohesion: 0.5
Nodes (3): Template-backed QMD rendering., Render a lightweight QMD report from the named template., render_qmd()

### Community 36 - "Community 36"
Cohesion: 0.67
Nodes (0): 

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): Shadow-only model registry.  These entries are visible to research and reporting

### Community 38 - "Community 38"
Cohesion: 1.0
Nodes (0): 

### Community 39 - "Community 39"
Cohesion: 1.0
Nodes (1): Train or initialize the model and return metadata.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Generate model predictions.

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Persist model artifacts to disk.

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Load model artifacts from disk.

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Return True when CUDA tooling appears to be available.

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Helius WebSocket URL (constructed from API key).

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Helius enhanced API base URL.

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Fit the preferred regime model, falling back to GMM when hmmlearn is absent.

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Predict latent regime states and per-row probabilities.

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): SQLAlchemy database URL.

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): Parquet data directory.

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Helius WebSocket URL (constructed from API key).

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): Helius enhanced API base URL.

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Jupiter API base URL.

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): Massive REST API base URL.

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): Massive flat-file host for daily downloadable crypto data.

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Stable symbol hints for the pinned mint universe.

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): Get cached settings instance.

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Allow a simple comma-separated env var for tracked addresses.

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): Normalize blank values and allow a simple string path.

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Populate Coinbase credentials from an env-like secrets file when present.

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): SQLAlchemy database URL.

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Raw data landing directory.

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): Parquet data directory.

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Coinbase Advanced Trade API base URL.

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (1): Append-only paper fill receipt tied to explicit upstream provenance.

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (1): Current paper position state for one mint inside one paper session.

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (1): Settlement-owned report derived from paper sessions, fills, and positions.

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): Research experiment tracking.

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): Experiment metric values.

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): Research-owned advisory comparison between shadow context and paper outcomes.

## Knowledge Gaps
- **168 isolated node(s):** `Add the first explicit backtest truth ledger tables.  Revision ID: 010 Revises:`, `Add the first bounded feature materialization table.  Revision ID: 003 Revises:`, `Add global regime inputs and condition scoring truth tables.  Revision ID: 004 R`, `Add the first explicit paper settlement ledger tables.  Revision ID: 007 Revises`, `Add proposal review truth.  Revision ID: 012 Revises: 011 Create Date: 2026-04-1` (+163 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 37`** (2 nodes): `shadow_only.py`, `Shadow-only model registry.  These entries are visible to research and reporting`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 38`** (2 nodes): `test_reporting_artifacts.py`, `test_reporting_artifacts_write_sql_receipts()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 39`** (1 nodes): `Train or initialize the model and return metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Generate model predictions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Persist model artifacts to disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Load model artifacts from disk.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Return True when CUDA tooling appears to be available.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Helius WebSocket URL (constructed from API key).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `Helius enhanced API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `Fit the preferred regime model, falling back to GMM when hmmlearn is absent.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Predict latent regime states and per-row probabilities.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `SQLAlchemy database URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `Parquet data directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Helius WebSocket URL (constructed from API key).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `Helius enhanced API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Jupiter API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `Massive REST API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `Massive flat-file host for daily downloadable crypto data.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Stable symbol hints for the pinned mint universe.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `Get cached settings instance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Allow a simple comma-separated env var for tracked addresses.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `Normalize blank values and allow a simple string path.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Populate Coinbase credentials from an env-like secrets file when present.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `SQLAlchemy database URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Raw data landing directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `Parquet data directory.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Coinbase Advanced Trade API base URL.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `Append-only paper fill receipt tied to explicit upstream provenance.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `Current paper position state for one mint inside one paper session.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `Settlement-owned report derived from paper sessions, fills, and positions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `Research experiment tracking.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `Experiment metric values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `Research-owned advisory comparison between shadow context and paper outcomes.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Settings` connect `Community 2` to `Community 0`, `Community 1`, `Community 3`, `Community 4`, `Community 5`, `Community 9`?**
  _High betweenness centrality (0.295) - this node is a cross-community bridge._
- **Why does `read_text()` connect `Community 7` to `Community 9`, `Community 2`, `Community 3`?**
  _High betweenness centrality (0.059) - this node is a cross-community bridge._
- **Why does `Trajectory — advisory forecasting and scenario generation (scaffold).` connect `Community 6` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Are the 265 inferred relationships involving `Settings` (e.g. with `get_settings()` and `FredNormalizer`) actually correct?**
  _`Settings` has 265 INFERRED edges - model-reasoned connections that need verification._
- **Are the 103 inferred relationships involving `IngestRun` (e.g. with `D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic` and `D5 Trading Engine — crypto data capture + research engine.`) actually correct?**
  _`IngestRun` has 103 INFERRED edges - model-reasoned connections that need verification._
- **Are the 101 inferred relationships involving `SourceHealthEvent` (e.g. with `D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic` and `D5 Trading Engine — crypto data capture + research engine.`) actually correct?**
  _`SourceHealthEvent` has 101 INFERRED edges - model-reasoned connections that need verification._
- **Are the 53 inferred relationships involving `ShadowRunner` (e.g. with `D5 Trading Engine — CLI Entry Point  Commands: - d5 init         : Apply Alembic` and `D5 Trading Engine — crypto data capture + research engine.`) actually correct?**
  _`ShadowRunner` has 53 INFERRED edges - model-reasoned connections that need verification._