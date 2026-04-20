use std::collections::{BTreeMap, HashMap};
use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use anyhow::{Context, Result};
use chrono::Utc;
use regex::Regex;
use rusqlite::{Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use walkdir::{DirEntry, WalkDir};

#[derive(Debug, Clone)]
pub struct CoverageArgs {
    pub repo_root: PathBuf,
    pub db_path: PathBuf,
    pub regimen: String,
    pub write_quickread: bool,
}

#[derive(Debug, Clone)]
pub struct FunnelArgs {
    pub repo_root: PathBuf,
    pub db_path: PathBuf,
    pub run: String,
    pub window_days: Option<i64>,
    pub write_quickread: bool,
}

#[derive(Debug, Clone)]
pub struct RepoArgs {
    pub repo_root: PathBuf,
    pub write_quickread: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepoRef {
    pub git_commit: String,
    pub branch: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Quickread {
    pub tool: String,
    pub version: String,
    pub created_at_utc: String,
    pub repo_ref: RepoRef,
    pub verdict: String,
    pub primary_failure_surface: Option<String>,
    pub summary: Value,
    pub details: Value,
    pub recommended_next_actions: Vec<Value>,
}

#[derive(Debug, Clone, Copy)]
struct Regimen {
    expected_days: i64,
    required_history_days: i64,
}

pub fn run_coverage(args: CoverageArgs) -> Result<Quickread> {
    let regimen = regimen(&args.regimen);
    let conn = Connection::open(&args.db_path)
        .with_context(|| format!("opening SQLite database {}", args.db_path.display()))?;
    let sql_days_present = count_distinct(&conn, "market_candle", "event_date_utc")?;
    let feature_days_present = count_distinct(
        &conn,
        "feature_global_regime_input_15m_v1",
        "event_date_utc",
    )?;
    let sql_range = date_range(&conn, "market_candle", "event_date_utc")?;
    let feature_range = date_range(
        &conn,
        "feature_global_regime_input_15m_v1",
        "event_date_utc",
    )?;

    let (verdict, surface, action) = if sql_days_present < regimen.required_history_days {
        (
            "FAIL",
            Some("data_coverage_gap"),
            json!({
                "action": "hydrate_training_window",
                "reason": "SQL market-candle days are below the regimen requirement"
            }),
        )
    } else if feature_days_present < regimen.required_history_days {
        (
            "FAIL",
            Some("feature_materialization_gap"),
            json!({
                "action": "repair_feature_window",
                "reason": "Feature days are below the regimen requirement"
            }),
        )
    } else {
        (
            "PASS",
            None,
            json!({
                "action": "run_gate_funnel",
                "reason": "Training-window coverage is sufficient for diagnostics"
            }),
        )
    };

    let report = quickread(
        &args.repo_root,
        "d5v.coverage",
        verdict,
        surface,
        json!({
            "regimen": args.regimen,
            "expected_days": regimen.expected_days,
            "required_history_days": regimen.required_history_days,
            "sql_days_present": sql_days_present,
            "feature_days_present": feature_days_present,
            "coverage_pct": pct(sql_days_present, regimen.expected_days),
            "feature_coverage_pct": pct(feature_days_present, regimen.expected_days),
        }),
        json!({
            "db_path": args.db_path,
            "sql_date_range": sql_range,
            "feature_date_range": feature_range,
        }),
        vec![action],
    );
    maybe_write_quickread(&args.repo_root, "coverage", &report, args.write_quickread)?;
    Ok(report)
}

pub fn run_funnel(args: FunnelArgs) -> Result<Quickread> {
    let conn = Connection::open(&args.db_path)
        .with_context(|| format!("opening SQLite database {}", args.db_path.display()))?;
    let loop_run_id = resolve_loop_run(&conn, &args.run)?;
    let decisions = load_decisions(&conn, &loop_run_id, args.window_days)?;
    let mut reason_counts: BTreeMap<String, i64> = BTreeMap::new();
    let mut surface_counts: HashMap<String, i64> = HashMap::new();

    let mut valid_conditions = 0_i64;
    let mut policy_allowed = 0_i64;
    let mut risk_approved = 0_i64;
    let mut quote_available = 0_i64;
    let mut paper_filled = 0_i64;
    let mut no_trade_cycles = 0_i64;

    for decision in &decisions {
        if decision.decision_type == "no_trade" {
            no_trade_cycles += 1;
        }
        if decision.decision_type == "paper_trade_opened"
            || decision.decision_type == "paper_trade_closed"
        {
            paper_filled += 1;
        }
        if decision.condition_run_id {
            valid_conditions += 1;
        }
        if decision.policy_trace_id || decision.decision_type.starts_with("paper_trade") {
            policy_allowed += 1;
        }
        if decision.risk_verdict_id || decision.decision_type.starts_with("paper_trade") {
            risk_approved += 1;
        }
        if decision.quote_snapshot_id || decision.decision_type.starts_with("paper_trade") {
            quote_available += 1;
        }
        let mut surfaces_this_decision: HashMap<String, bool> = HashMap::new();
        for reason in parse_reason_codes(&decision.reason_codes_json) {
            *reason_counts.entry(reason.clone()).or_insert(0) += 1;
            if decision.decision_type == "no_trade" {
                surfaces_this_decision.insert(reason_surface(&reason).to_string(), true);
            }
        }
        for surface in surfaces_this_decision.keys() {
            *surface_counts.entry(surface.clone()).or_insert(0) += 1;
        }
    }

    let primary_surface = ranked_surface(&surface_counts);
    let cycles = decisions.len() as i64;
    let strategy_candidates = (cycles
        - surface_counts
            .get("strategy_candidate_generation_failure")
            .copied()
            .unwrap_or(0))
    .max(0);
    let verdict = if paper_filled > 0 && primary_surface.is_none() {
        "PASS"
    } else {
        "FAIL"
    };
    let surface = primary_surface.or_else(|| {
        if cycles == 0 {
            Some("decision_funnel_missing".to_string())
        } else if paper_filled == 0 {
            Some("strategy_candidate_generation_failure".to_string())
        } else {
            None
        }
    });

    let report = quickread(
        &args.repo_root,
        "d5v.funnel",
        verdict,
        surface.clone(),
        json!({
            "loop_run_id": loop_run_id,
            "cycles": cycles,
            "valid_features": valid_conditions,
            "valid_conditions": valid_conditions,
            "strategy_candidates": strategy_candidates,
            "policy_allowed": policy_allowed,
            "risk_approved": risk_approved,
            "quote_available": quote_available,
            "paper_filled": paper_filled,
            "no_trade_cycles": no_trade_cycles,
        }),
        json!({
            "db_path": args.db_path,
            "window_days": args.window_days,
            "top_reason_codes": ranked_reasons(&reason_counts),
            "surface_counts": surface_counts,
        }),
        vec![json!({
            "action": recommended_action(surface.as_deref()),
            "reason": "Primary decision-funnel failure surface"
        })],
    );
    let name = if args.window_days.is_some() {
        "no_trades"
    } else {
        "funnel"
    };
    maybe_write_quickread(&args.repo_root, name, &report, args.write_quickread)?;
    Ok(report)
}

pub fn run_boundaries(args: RepoArgs) -> Result<Quickread> {
    let mut violations = Vec::new();
    let src = args.repo_root.join("src/d5_trading_engine");
    if src.exists() {
        for entry in walk_python(&src) {
            let entry = entry?;
            let path = entry.path();
            let rel = path.strip_prefix(&args.repo_root).unwrap_or(path);
            let text = fs::read_to_string(path).unwrap_or_default();
            let rel_text = rel.to_string_lossy();
            if rel_text.contains("/runtime/") && text.contains("d5_trading_engine.research_loop") {
                violations.push(json!({
                    "file": rel_text,
                    "rule": "runtime_must_not_import_research_loop",
                    "import": "d5_trading_engine.research_loop"
                }));
            }
            if rel_text.contains("/risk/") && text.contains("d5_trading_engine.research_loop") {
                violations.push(json!({
                    "file": rel_text,
                    "rule": "risk_must_not_import_research_loop",
                    "import": "d5_trading_engine.research_loop"
                }));
            }
            if rel_text.contains("/runtime/") && text.contains("training.") {
                violations.push(json!({
                    "file": rel_text,
                    "rule": "runtime_must_not_import_training_control_plane",
                    "import": "training"
                }));
            }
        }
    }

    let verdict = if violations.is_empty() {
        "PASS"
    } else {
        "FAIL"
    };
    let surface = (!violations.is_empty()).then(|| "layer_boundary_violation".to_string());
    let actions = if violations.is_empty() {
        Vec::new()
    } else {
        vec![json!({
            "action": "restore_layer_boundary",
            "reason": "Runtime/risk surfaces must not depend on research or training control-plane code"
        })]
    };
    let report = quickread(
        &args.repo_root,
        "d5v.boundaries",
        verdict,
        surface,
        json!({ "violation_count": violations.len() }),
        json!({ "violations": violations }),
        actions,
    );
    maybe_write_quickread(&args.repo_root, "boundaries", &report, args.write_quickread)?;
    Ok(report)
}

pub fn run_schema_check(args: RepoArgs) -> Result<Quickread> {
    let roots = [
        args.repo_root.join(".ai/schemas"),
        args.repo_root.join(".ai/policies"),
    ];
    let mut checked = 0_usize;
    let mut invalid = Vec::new();
    for root in roots {
        if !root.exists() {
            continue;
        }
        for entry in WalkDir::new(root).into_iter().filter_entry(not_ignored) {
            let entry = entry?;
            if !entry.file_type().is_file()
                || entry.path().extension().and_then(|x| x.to_str()) != Some("json")
            {
                continue;
            }
            checked += 1;
            let rel = entry
                .path()
                .strip_prefix(&args.repo_root)
                .unwrap_or(entry.path())
                .display()
                .to_string();
            match fs::read_to_string(entry.path())
                .ok()
                .and_then(|text| serde_json::from_str::<Value>(&text).ok())
            {
                Some(_) => {}
                None => invalid.push(json!({ "file": rel, "error": "invalid_json" })),
            }
        }
    }
    let verdict = if checked > 0 && invalid.is_empty() {
        "PASS"
    } else {
        "FAIL"
    };
    let surface = (verdict == "FAIL").then(|| "schema_gap".to_string());
    let actions = if verdict == "FAIL" {
        vec![json!({
            "action": "repair_agent_contract_json",
            "reason": "Agent schemas and policies must parse before proposal work"
        })]
    } else {
        Vec::new()
    };
    let report = quickread(
        &args.repo_root,
        "d5v.schema_check",
        verdict,
        surface,
        json!({ "checked_files": checked, "invalid_files": invalid.len() }),
        json!({ "invalid": invalid }),
        actions,
    );
    maybe_write_quickread(
        &args.repo_root,
        "schema_check",
        &report,
        args.write_quickread,
    )?;
    Ok(report)
}

pub fn run_secrets(args: RepoArgs) -> Result<Quickread> {
    let solana_array = Regex::new(r"(?m)^\s*SOLANA_PRIVATE_KEY\s*=\s*\[").unwrap();
    let private_key_block =
        Regex::new(r"(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----\s+[A-Za-z0-9+/=\r\n]{40,}\s+-----END [A-Z ]*PRIVATE KEY-----")
            .unwrap();
    let mut findings = Vec::new();
    for entry in WalkDir::new(&args.repo_root)
        .into_iter()
        .filter_entry(not_ignored)
    {
        let entry = entry?;
        if !entry.file_type().is_file() {
            continue;
        }
        let path = entry.path();
        if fs::metadata(path)
            .map(|meta| meta.len() > 2_000_000)
            .unwrap_or(true)
        {
            continue;
        }
        let text = fs::read_to_string(path).unwrap_or_default();
        if solana_array.is_match(&text) || private_key_block.is_match(&text) {
            let rel = path
                .strip_prefix(&args.repo_root)
                .unwrap_or(path)
                .display()
                .to_string();
            findings.push(json!({ "file": rel, "rule": "tracked_secret_material" }));
        }
    }

    let verdict = if findings.is_empty() { "PASS" } else { "FAIL" };
    let surface = (!findings.is_empty()).then(|| "secret_material_exposed".to_string());
    let actions = if findings.is_empty() {
        Vec::new()
    } else {
        vec![json!({
            "action": "remove_tracked_secret_material",
            "reason": "Wallet and API secret material must not enter tracked files"
        })]
    };
    let report = quickread(
        &args.repo_root,
        "d5v.secrets",
        verdict,
        surface,
        json!({ "finding_count": findings.len() }),
        json!({ "findings": findings }),
        actions,
    );
    maybe_write_quickread(&args.repo_root, "secrets", &report, args.write_quickread)?;
    Ok(report)
}

fn quickread(
    repo_root: &Path,
    tool: &str,
    verdict: &str,
    primary_failure_surface: Option<impl Into<String>>,
    summary: Value,
    details: Value,
    recommended_next_actions: Vec<Value>,
) -> Quickread {
    Quickread {
        tool: tool.to_string(),
        version: "v1".to_string(),
        created_at_utc: Utc::now().to_rfc3339(),
        repo_ref: repo_ref(repo_root),
        verdict: verdict.to_string(),
        primary_failure_surface: primary_failure_surface.map(Into::into),
        summary,
        details,
        recommended_next_actions,
    }
}

fn maybe_write_quickread(
    repo_root: &Path,
    name: &str,
    report: &Quickread,
    enabled: bool,
) -> Result<()> {
    if !enabled {
        return Ok(());
    }
    let dir = repo_root.join(".ai/quickreads");
    fs::create_dir_all(&dir)?;
    fs::write(
        dir.join(format!("latest_{name}.json")),
        serde_json::to_vec_pretty(report)?,
    )?;
    Ok(())
}

fn repo_ref(repo_root: &Path) -> RepoRef {
    RepoRef {
        git_commit: git_output(repo_root, &["rev-parse", "--short", "HEAD"])
            .unwrap_or_else(|| "unknown".to_string()),
        branch: git_output(repo_root, &["branch", "--show-current"])
            .unwrap_or_else(|| "unknown".to_string()),
    }
}

fn git_output(repo_root: &Path, args: &[&str]) -> Option<String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(repo_root)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    let text = String::from_utf8(output.stdout).ok()?.trim().to_string();
    (!text.is_empty()).then_some(text)
}

fn regimen(name: &str) -> Regimen {
    match name {
        "full_730d" => Regimen {
            expected_days: 730,
            required_history_days: 455,
        },
        _ => Regimen {
            expected_days: 300,
            required_history_days: 300,
        },
    }
}

fn pct(numerator: i64, denominator: i64) -> f64 {
    if denominator <= 0 {
        return 0.0;
    }
    ((numerator as f64 / denominator as f64) * 10_000.0).round() / 10_000.0
}

fn count_distinct(conn: &Connection, table: &str, column: &str) -> Result<i64> {
    if !table_exists(conn, table)? {
        return Ok(0);
    }
    let sql = format!("SELECT COUNT(DISTINCT {column}) FROM {table} WHERE {column} IS NOT NULL");
    Ok(conn.query_row(&sql, [], |row| row.get::<_, i64>(0))?)
}

fn date_range(conn: &Connection, table: &str, column: &str) -> Result<Value> {
    if !table_exists(conn, table)? {
        return Ok(json!({ "start": null, "end": null }));
    }
    let sql = format!("SELECT MIN({column}), MAX({column}) FROM {table}");
    let (start, end): (Option<String>, Option<String>) =
        conn.query_row(&sql, [], |row| Ok((row.get(0)?, row.get(1)?)))?;
    Ok(json!({ "start": start, "end": end }))
}

fn table_exists(conn: &Connection, table: &str) -> Result<bool> {
    let found: Option<i64> = conn
        .query_row(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?1",
            [table],
            |row| row.get(0),
        )
        .optional()?;
    Ok(found.is_some())
}

fn resolve_loop_run(conn: &Connection, run: &str) -> Result<String> {
    if run != "latest" {
        if run == "latest-populated" || run == "latest-with-decisions" {
            return conn
                .query_row(
                    "SELECT r.loop_run_id \
                     FROM paper_practice_loop_run_v1 r \
                     JOIN paper_practice_decision_v1 d ON d.loop_run_id = r.loop_run_id \
                     GROUP BY r.loop_run_id, r.created_at, r.started_at \
                     HAVING COUNT(d.decision_id) > 0 \
                     ORDER BY r.created_at DESC, r.started_at DESC \
                     LIMIT 1",
                    [],
                    |row| row.get::<_, String>(0),
                )
                .optional()?
                .context("no populated paper practice loop run found");
        }
        return Ok(run.to_string());
    }
    conn.query_row(
        "SELECT loop_run_id FROM paper_practice_loop_run_v1 ORDER BY created_at DESC, started_at DESC LIMIT 1",
        [],
        |row| row.get::<_, String>(0),
    )
    .optional()?
    .context("no paper practice loop run found")
}

#[derive(Debug)]
struct DecisionRow {
    decision_type: String,
    condition_run_id: bool,
    policy_trace_id: bool,
    risk_verdict_id: bool,
    quote_snapshot_id: bool,
    reason_codes_json: String,
}

fn load_decisions(
    conn: &Connection,
    loop_run_id: &str,
    window_days: Option<i64>,
) -> Result<Vec<DecisionRow>> {
    let mut sql = String::from(
        "SELECT decision_type, condition_run_id, policy_trace_id, risk_verdict_id, quote_snapshot_id, reason_codes_json \
         FROM paper_practice_decision_v1 WHERE loop_run_id = ?1",
    );
    if let Some(days) = window_days {
        sql.push_str(&format!(
            " AND created_at >= datetime('now', '-{days} days')"
        ));
    }
    sql.push_str(" ORDER BY created_at ASC");
    let mut stmt = conn.prepare(&sql)?;
    let rows = stmt.query_map([loop_run_id], |row| {
        Ok(DecisionRow {
            decision_type: row.get::<_, String>(0)?,
            condition_run_id: row.get::<_, Option<String>>(1)?.is_some(),
            policy_trace_id: row.get::<_, Option<i64>>(2)?.is_some(),
            risk_verdict_id: row.get::<_, Option<i64>>(3)?.is_some(),
            quote_snapshot_id: row.get::<_, Option<i64>>(4)?.is_some(),
            reason_codes_json: row.get::<_, String>(5)?,
        })
    })?;
    rows.collect::<std::result::Result<Vec<_>, _>>()
        .map_err(Into::into)
}

fn parse_reason_codes(raw: &str) -> Vec<String> {
    serde_json::from_str::<Vec<String>>(raw).unwrap_or_default()
}

fn reason_surface(reason: &str) -> &'static str {
    if reason.starts_with("strategy_target_not_runtime_long")
        || reason.starts_with("strategy_regime_not_allowed")
        || reason.starts_with("strategy_selection_unavailable")
    {
        "strategy_candidate_generation_failure"
    } else if reason.starts_with("condition_confidence_below_profile_minimum") {
        "condition_churn_or_staleness"
    } else if reason.starts_with("regime_not_allowed")
        || reason.starts_with("profile_cooldown_active")
    {
        "policy_overblocking"
    } else if reason.starts_with("risk") {
        "risk_overblocking"
    } else if reason.starts_with("quote") {
        "quote_fill_unavailability"
    } else if reason.starts_with("freshness_authorization_failed")
        || reason.starts_with("source_freshness_block")
    {
        "feature_materialization_gap"
    } else if reason.starts_with("paper_ready_receipt_not_actionable") {
        "data_coverage_gap"
    } else {
        "unknown"
    }
}

fn ranked_surface(counts: &HashMap<String, i64>) -> Option<String> {
    let mut ranked: Vec<_> = counts.iter().collect();
    ranked.sort_by_key(|(surface, count)| (surface_priority(surface), -*count));
    ranked.first().map(|(surface, _)| (*surface).clone())
}

fn surface_priority(surface: &str) -> i64 {
    match surface {
        "strategy_candidate_generation_failure" => 0,
        "condition_churn_or_staleness" => 1,
        "policy_overblocking" => 2,
        "risk_overblocking" => 3,
        "quote_fill_unavailability" => 4,
        "feature_materialization_gap" => 5,
        "data_coverage_gap" => 6,
        "decision_funnel_missing" => 7,
        _ => 99,
    }
}

fn ranked_reasons(counts: &BTreeMap<String, i64>) -> Vec<Value> {
    let mut ranked: Vec<_> = counts.iter().collect();
    ranked.sort_by(|a, b| b.1.cmp(a.1).then_with(|| a.0.cmp(b.0)));
    ranked
        .into_iter()
        .map(|(reason_code, count)| json!({ "reason_code": reason_code, "count": count }))
        .collect()
}

fn recommended_action(surface: Option<&str>) -> &'static str {
    match surface {
        Some("strategy_candidate_generation_failure") => "run_baseline_candidate_strategy",
        Some("condition_churn_or_staleness") => "run_condition_threshold_shadow_overlay",
        Some("policy_overblocking") => "run_policy_eligibility_comparison",
        Some("risk_overblocking") => "run_risk_rejection_histogram",
        Some("quote_fill_unavailability") => "audit_quote_freshness",
        Some("data_coverage_gap") => "hydrate_training_window",
        Some("decision_funnel_missing") => "run_or_repair_decision_funnel",
        Some("feature_materialization_gap") => "repair_feature_window",
        Some("layer_boundary_violation") => "restore_layer_boundary",
        Some("schema_gap") => "repair_agent_contract_json",
        Some("secret_material_exposed") => "remove_tracked_secret_material",
        _ => "inspect_raw_receipts",
    }
}

fn walk_python(root: &Path) -> impl Iterator<Item = walkdir::Result<DirEntry>> {
    WalkDir::new(root)
        .into_iter()
        .filter_entry(not_ignored)
        .filter(|entry| {
            entry
                .as_ref()
                .map(|e| {
                    e.file_type().is_file()
                        && e.path().extension().and_then(|x| x.to_str()) == Some("py")
                })
                .unwrap_or(true)
        })
}

fn not_ignored(entry: &DirEntry) -> bool {
    let name = entry.file_name().to_string_lossy();
    !matches!(
        name.as_ref(),
        ".git" | "data" | "target" | ".venv" | "venv" | "__pycache__" | ".pytest_cache"
    )
}
