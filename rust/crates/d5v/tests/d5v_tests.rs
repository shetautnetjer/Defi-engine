use std::fs;
use std::path::Path;

use d5v::commands::{
    run_boundaries, run_coverage, run_funnel, run_schema_check, run_secrets, CoverageArgs,
    FunnelArgs, RepoArgs,
};
use rusqlite::Connection;
use tempfile::TempDir;

fn write_file(path: &Path, contents: &str) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).unwrap();
    }
    fs::write(path, contents).unwrap();
}

fn fixture_repo() -> TempDir {
    let temp = TempDir::new().unwrap();
    fs::create_dir_all(temp.path().join(".ai/schemas")).unwrap();
    fs::create_dir_all(temp.path().join(".ai/policies")).unwrap();
    write_file(
        temp.path()
            .join(".ai/schemas/example.schema.json")
            .as_path(),
        "{}",
    );
    write_file(
        temp.path().join(".ai/policies/example.v1.json").as_path(),
        "{}",
    );
    temp
}

fn fixture_db(path: &Path) {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).unwrap();
    }
    let conn = Connection::open(path).unwrap();
    conn.execute_batch(
        r#"
        CREATE TABLE market_candle (event_date_utc TEXT);
        CREATE TABLE feature_global_regime_input_15m_v1 (event_date_utc TEXT);
        CREATE TABLE paper_practice_loop_run_v1 (
            loop_run_id TEXT,
            created_at TEXT,
            started_at TEXT
        );
        CREATE TABLE paper_practice_decision_v1 (
            decision_id TEXT,
            loop_run_id TEXT,
            decision_type TEXT,
            condition_run_id TEXT,
            policy_trace_id INTEGER,
            risk_verdict_id INTEGER,
            quote_snapshot_id INTEGER,
            reason_codes_json TEXT,
            created_at TEXT
        );
        INSERT INTO feature_global_regime_input_15m_v1 VALUES ('2026-01-01'), ('2026-01-02');
        INSERT INTO paper_practice_loop_run_v1 VALUES ('loop_1', '2026-01-03T00:00:00Z', '2026-01-03T00:00:00Z');
        INSERT INTO paper_practice_decision_v1 VALUES (
            'decision_1',
            'loop_1',
            'no_trade',
            'condition_1',
            NULL,
            NULL,
            NULL,
            '["strategy_target_not_runtime_long:flat"]',
            '2026-01-03T00:00:00Z'
        );
        "#,
    )
    .unwrap();
    let tx = conn.unchecked_transaction().unwrap();
    for day in 1..=300 {
        tx.execute(
            "INSERT INTO market_candle VALUES (?1)",
            [format!("2026-01-{day:02}")],
        )
        .unwrap();
    }
    tx.commit().unwrap();
}

fn fixture_db_without_decisions(path: &Path) {
    fixture_db(path);
    let conn = Connection::open(path).unwrap();
    conn.execute("DELETE FROM paper_practice_decision_v1", [])
        .unwrap();
}

#[test]
fn coverage_reports_degraded_feature_gap_and_writes_quickread() {
    let repo = fixture_repo();
    let db_path = repo.path().join("data/db/d5.db");
    fixture_db(&db_path);

    let report = run_coverage(CoverageArgs {
        repo_root: repo.path().to_path_buf(),
        db_path,
        regimen: "quickstart_300d".to_string(),
        write_quickread: true,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.coverage");
    assert_eq!(report.verdict, "FAIL");
    assert_eq!(
        report.primary_failure_surface.as_deref(),
        Some("feature_materialization_gap")
    );
    assert!(repo
        .path()
        .join(".ai/quickreads/latest_coverage.json")
        .exists());
}

#[test]
fn funnel_reports_strategy_candidate_failure() {
    let repo = fixture_repo();
    let db_path = repo.path().join("data/db/d5.db");
    fixture_db(&db_path);

    let report = run_funnel(FunnelArgs {
        repo_root: repo.path().to_path_buf(),
        db_path,
        run: "latest".to_string(),
        window_days: None,
        write_quickread: true,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.funnel");
    assert_eq!(report.verdict, "FAIL");
    assert_eq!(
        report.primary_failure_surface.as_deref(),
        Some("strategy_candidate_generation_failure")
    );
    assert!(repo
        .path()
        .join(".ai/quickreads/latest_funnel.json")
        .exists());
}

#[test]
fn funnel_reports_missing_decision_funnel_separately_from_data_coverage() {
    let repo = fixture_repo();
    let db_path = repo.path().join("data/db/d5.db");
    fixture_db_without_decisions(&db_path);

    let report = run_funnel(FunnelArgs {
        repo_root: repo.path().to_path_buf(),
        db_path,
        run: "latest".to_string(),
        window_days: Some(730),
        write_quickread: false,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.funnel");
    assert_eq!(report.verdict, "FAIL");
    assert_eq!(
        report.primary_failure_surface.as_deref(),
        Some("decision_funnel_missing")
    );
    assert_eq!(
        report.recommended_next_actions[0]["action"],
        "run_or_repair_decision_funnel"
    );
}

#[test]
fn boundaries_reject_runtime_importing_research_loop() {
    let repo = fixture_repo();
    write_file(
        repo.path()
            .join("src/d5_trading_engine/runtime/cycle/runner.py")
            .as_path(),
        "from d5_trading_engine.research_loop.training_runtime import TrainingRuntime\n",
    );

    let report = run_boundaries(RepoArgs {
        repo_root: repo.path().to_path_buf(),
        write_quickread: false,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.boundaries");
    assert_eq!(report.verdict, "FAIL");
    assert_eq!(
        report.primary_failure_surface.as_deref(),
        Some("layer_boundary_violation")
    );
}

#[test]
fn schema_check_fails_invalid_json() {
    let repo = fixture_repo();
    write_file(
        repo.path().join(".ai/schemas/broken.schema.json").as_path(),
        "{not-json",
    );

    let report = run_schema_check(RepoArgs {
        repo_root: repo.path().to_path_buf(),
        write_quickread: false,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.schema_check");
    assert_eq!(report.verdict, "FAIL");
    assert_eq!(
        report.primary_failure_surface.as_deref(),
        Some("schema_gap")
    );
}

#[test]
fn secrets_flags_tracked_private_key_material() {
    let repo = fixture_repo();
    write_file(
        repo.path().join("config/leak.env").as_path(),
        "SOLANA_PRIVATE_KEY=[1,2,3]\n",
    );

    let report = run_secrets(RepoArgs {
        repo_root: repo.path().to_path_buf(),
        write_quickread: false,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.secrets");
    assert_eq!(report.verdict, "FAIL");
    assert_eq!(
        report.primary_failure_surface.as_deref(),
        Some("secret_material_exposed")
    );
}

#[test]
fn secrets_ignores_private_key_marker_test_snippets() {
    let repo = fixture_repo();
    write_file(
        repo.path().join("tests/test_config.py").as_path(),
        r#"assert value.startswith("-----BEGIN EC PRIVATE KEY-----\n")"#,
    );

    let report = run_secrets(RepoArgs {
        repo_root: repo.path().to_path_buf(),
        write_quickread: false,
    })
    .unwrap();

    assert_eq!(report.tool, "d5v.secrets");
    assert_eq!(report.verdict, "PASS");
    assert_eq!(report.primary_failure_surface, None);
}
