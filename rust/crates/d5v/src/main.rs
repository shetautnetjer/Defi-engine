use std::path::PathBuf;

use anyhow::Result;
use clap::{Parser, Subcommand};
use d5v::commands::{
    run_boundaries, run_coverage, run_funnel, run_schema_check, run_secrets, CoverageArgs,
    FunnelArgs, RepoArgs,
};

#[derive(Debug, Parser)]
#[command(name = "d5v")]
#[command(about = "D5 deterministic verifier quickreads")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Subcommand)]
enum Commands {
    Coverage {
        #[arg(long, default_value = ".")]
        repo_root: PathBuf,
        #[arg(long, default_value = "data/db/d5.db")]
        db_path: PathBuf,
        #[arg(long, default_value = "full_730d")]
        regimen: String,
        #[arg(long)]
        no_write_quickread: bool,
        #[arg(long)]
        json: bool,
    },
    Funnel {
        #[arg(long, default_value = ".")]
        repo_root: PathBuf,
        #[arg(long, default_value = "data/db/d5.db")]
        db_path: PathBuf,
        #[arg(long, default_value = "latest")]
        run: String,
        #[arg(long)]
        no_write_quickread: bool,
        #[arg(long)]
        json: bool,
    },
    #[command(name = "no-trades")]
    NoTrades {
        #[arg(long, default_value = ".")]
        repo_root: PathBuf,
        #[arg(long, default_value = "data/db/d5.db")]
        db_path: PathBuf,
        #[arg(long, default_value = "latest")]
        run: String,
        #[arg(long, default_value = "730d")]
        window: String,
        #[arg(long)]
        no_write_quickread: bool,
        #[arg(long)]
        json: bool,
    },
    Boundaries {
        #[arg(long, default_value = ".")]
        repo_root: PathBuf,
        #[arg(long)]
        no_write_quickread: bool,
        #[arg(long)]
        json: bool,
    },
    #[command(name = "schema-check")]
    SchemaCheck {
        #[arg(long, default_value = ".")]
        repo_root: PathBuf,
        #[arg(long)]
        all: bool,
        #[arg(long)]
        no_write_quickread: bool,
        #[arg(long)]
        json: bool,
    },
    Secrets {
        #[arg(long, default_value = ".")]
        repo_root: PathBuf,
        #[arg(long)]
        no_write_quickread: bool,
        #[arg(long)]
        json: bool,
    },
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let report = match cli.command {
        Commands::Coverage {
            repo_root,
            db_path,
            regimen,
            no_write_quickread,
            json: _,
        } => run_coverage(CoverageArgs {
            repo_root,
            db_path,
            regimen,
            write_quickread: !no_write_quickread,
        })?,
        Commands::Funnel {
            repo_root,
            db_path,
            run,
            no_write_quickread,
            json: _,
        } => run_funnel(FunnelArgs {
            repo_root,
            db_path,
            run,
            window_days: None,
            write_quickread: !no_write_quickread,
        })?,
        Commands::NoTrades {
            repo_root,
            db_path,
            run,
            window,
            no_write_quickread,
            json: _,
        } => run_funnel(FunnelArgs {
            repo_root,
            db_path,
            run,
            window_days: Some(parse_window_days(&window)),
            write_quickread: !no_write_quickread,
        })?,
        Commands::Boundaries {
            repo_root,
            no_write_quickread,
            json: _,
        } => run_boundaries(RepoArgs {
            repo_root,
            write_quickread: !no_write_quickread,
        })?,
        Commands::SchemaCheck {
            repo_root,
            all: _,
            no_write_quickread,
            json: _,
        } => run_schema_check(RepoArgs {
            repo_root,
            write_quickread: !no_write_quickread,
        })?,
        Commands::Secrets {
            repo_root,
            no_write_quickread,
            json: _,
        } => run_secrets(RepoArgs {
            repo_root,
            write_quickread: !no_write_quickread,
        })?,
    };
    println!("{}", serde_json::to_string_pretty(&report)?);
    Ok(())
}

fn parse_window_days(window: &str) -> i64 {
    window
        .strip_suffix('d')
        .unwrap_or(window)
        .parse::<i64>()
        .unwrap_or(730)
}
