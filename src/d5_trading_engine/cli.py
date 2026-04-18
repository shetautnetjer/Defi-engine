"""
D5 Trading Engine — CLI Entry Point

Commands:
- d5 init         : Apply Alembic migrations to head
- d5 capture      : Run data capture for one or all providers
- d5 materialize-features : Materialize deterministic feature tables
- d5 score-conditions : Score bounded market conditions
- d5 run-shadow   : Run shadow ML evaluation lanes
- d5 run-label-program : Run canonical label-program scoring
- d5 run-strategy-eval : Run governed strategy challenger scoring
- d5 run-paper-cycle : Run one bounded paper-trading cycle
- d5 compare-proposals : Rank reviewed proposals and optionally choose the next bounded experiment
- d5 capture massive-minute-aggs --date YYYY-MM-DD : Replay historical Massive minute bars
- d5 status       : Show engine health and ingest run stats
- d5 sync-duckdb  : Sync canonical truth tables to DuckDB mirror
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click

from d5_trading_engine.common.logging import get_logger, setup_logging
from d5_trading_engine.config.settings import get_settings

log = get_logger(__name__)

_CAPTURE_CHOICES = [
    "jupiter-tokens",
    "jupiter-prices",
    "jupiter-quotes",
    "helius-transactions",
    "helius-discovery",
    "helius-ws-events",
    "coinbase-products",
    "coinbase-candles",
    "coinbase-market-trades",
    "coinbase-book",
    "fred-series",
    "fred-observations",
    "massive-crypto",
    "massive-minute-aggs",
    "all",
]

_FEATURE_SET_CHOICES = [
    "global-regime-inputs-15m-v1",
    "spot-chain-macro-v1",
]
_CONDITION_SET_CHOICES = [
    "global-regime-v1",
]
_SHADOW_RUN_CHOICES = [
    "intraday-meta-stack-v1",
    "regime-model-compare-v1",
]
_LABEL_PROGRAM_CHOICES = [
    "canonical-direction-v1",
]
_STRATEGY_EVAL_CHOICES = [
    "governed-challengers-v1",
]


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """D5 Trading Engine — crypto data capture + research engine."""
    level = "DEBUG" if verbose else "INFO"
    setup_logging(level=level)


@cli.command()
def init() -> None:
    """Apply Alembic migrations to the canonical truth database."""
    from d5_trading_engine.storage.truth.engine import run_migrations_to_head

    settings = get_settings()
    click.echo(f"Applying migrations to database at {settings.db_path}")

    try:
        run_migrations_to_head(settings)
        click.echo("✓ Database migrations applied to head.")
    except Exception as exc:
        click.echo(f"✗ Database migration failed: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("provider", type=click.Choice(_CAPTURE_CHOICES, case_sensitive=False))
@click.option(
    "--date",
    "date_str",
    default=None,
    help="Optional UTC date for historical flat-file capture, in YYYY-MM-DD format.",
)
def capture(provider: str, date_str: str | None) -> None:
    """Run data capture for a specific provider or all."""
    from d5_trading_engine.capture.runner import CaptureRunner

    settings = get_settings()
    runner = CaptureRunner(settings)

    async def _run() -> None:
        try:
            if provider in {"jupiter-tokens", "all"}:
                run_id = await runner.capture_jupiter_tokens()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Jupiter tokens: {run_id}")

            if provider in {"jupiter-prices", "all"}:
                run_id = await runner.capture_jupiter_prices()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Jupiter prices: {run_id}")

            if provider in {"jupiter-quotes", "all"}:
                run_id = await runner.capture_jupiter_quotes()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Jupiter quotes: {run_id}")

            if provider in {"helius-transactions", "all"}:
                run_id = await runner.capture_helius_transactions()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Helius transactions: {run_id}")

            if provider in {"helius-discovery", "all"}:
                run_id = await runner.capture_helius_discovery()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Helius discovery: {run_id}")

            if provider in {"helius-ws-events"}:
                run_id = await runner.capture_helius_ws_events()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Helius ws events: {run_id}")

            if provider in {"coinbase-products", "all"}:
                run_id = await runner.capture_coinbase_products()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Coinbase products: {run_id}")

            if provider in {"coinbase-candles", "all"}:
                run_id = await runner.capture_coinbase_candles()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Coinbase candles: {run_id}")

            if provider in {"coinbase-market-trades", "all"}:
                run_id = await runner.capture_coinbase_market_trades()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Coinbase market trades: {run_id}")

            if provider in {"coinbase-book", "all"}:
                run_id = await runner.capture_coinbase_book()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Coinbase book: {run_id}")

            if provider in {"fred-series", "all"}:
                run_id = runner.capture_fred_series()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ FRED series: {run_id}")

            if provider in {"fred-observations", "all"}:
                run_id = runner.capture_fred_observations()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ FRED observations: {run_id}")

            if provider in {"massive-crypto", "all"}:
                run_id = await runner.capture_massive_crypto()
                runner.write_capture_receipts(run_id, context={"requested_provider": provider})
                click.echo(f"  ✓ Massive crypto: {run_id}")

            if provider == "massive-minute-aggs" or (provider == "all" and date_str):
                if provider == "massive-minute-aggs" and not date_str:
                    raise click.ClickException(
                        "--date YYYY-MM-DD is required for massive-minute-aggs capture."
                    )
                run_id = await runner.capture_massive_minute_aggs(date_str)
                runner.write_capture_receipts(
                    run_id,
                    context={"requested_provider": provider, "date": date_str},
                )
                click.echo(f"  ✓ Massive minute aggs: {run_id}")
        except Exception as exc:
            click.echo(f"  ✗ Capture failed: {exc}", err=True)
            sys.exit(1)

    click.echo(f"Starting capture: {provider}")
    asyncio.run(_run())
    click.echo("Capture complete.")


@cli.command("materialize-features")
@click.argument("feature_set", type=click.Choice(_FEATURE_SET_CHOICES, case_sensitive=False))
def materialize_features(feature_set: str) -> None:
    """Materialize a deterministic feature set from canonical truth."""
    from d5_trading_engine.features.materializer import FeatureMaterializer

    materializer = FeatureMaterializer(get_settings())

    try:
        if feature_set == "global-regime-inputs-15m-v1":
            run_id, row_count = materializer.materialize_global_regime_inputs_15m_v1()
            click.echo(f"✓ global_regime_inputs_15m_v1: {run_id} rows={row_count}")
            return
        if feature_set == "spot-chain-macro-v1":
            run_id, row_count = materializer.materialize_spot_chain_macro_v1()
            click.echo(f"✓ spot_chain_macro_v1: {run_id} rows={row_count}")
            return
        raise click.ClickException(f"Unsupported feature set: {feature_set}")
    except Exception as exc:
        click.echo(f"✗ Feature materialization failed: {exc}", err=True)
        sys.exit(1)


@cli.command("score-conditions")
@click.argument("condition_set", type=click.Choice(_CONDITION_SET_CHOICES, case_sensitive=False))
def score_conditions(condition_set: str) -> None:
    """Score a bounded condition set from deterministic feature inputs."""
    from d5_trading_engine.condition.scorer import ConditionScorer

    scorer = ConditionScorer(get_settings())

    try:
        if condition_set == "global-regime-v1":
            result = scorer.score_global_regime_v1()
            latest = result["latest_snapshot"]
            click.echo(
                "✓ global_regime_v1: "
                f"{result['run_id']} regime={latest['semantic_regime']} "
                f"confidence={latest['confidence']:.3f} model={result['model_family']}"
            )
            return
        raise click.ClickException(f"Unsupported condition set: {condition_set}")
    except Exception as exc:
        click.echo(f"✗ Condition scoring failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-shadow")
@click.argument("shadow_run", type=click.Choice(_SHADOW_RUN_CHOICES, case_sensitive=False))
def run_shadow(shadow_run: str) -> None:
    """Run a bounded shadow ML evaluation lane."""
    from d5_trading_engine.research_loop.regime_model_compare import (
        RegimeModelComparator,
    )
    from d5_trading_engine.research_loop.shadow_runner import ShadowRunner

    runner = ShadowRunner(get_settings())
    comparator = RegimeModelComparator(get_settings())

    try:
        if shadow_run == "intraday-meta-stack-v1":
            result = runner.run_intraday_meta_stack_v1()
            click.echo(
                "✓ intraday_meta_stack_v1: "
                f"{result['run_id']} artifacts={result['artifact_dir']} "
                f"chronos={result['chronos_status']}"
            )
            return
        if shadow_run == "regime-model-compare-v1":
            result = comparator.run_regime_model_compare_v1()
            click.echo(
                "✓ regime_model_compare_v1: "
                f"{result['run_id']} artifacts={result['artifact_dir']} "
                f"recommended={result['recommended_candidate']} "
                f"proposal={result['proposal_status']}"
            )
            return
        raise click.ClickException(f"Unsupported shadow run: {shadow_run}")
    except Exception as exc:
        click.echo(f"✗ Shadow run failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-label-program")
@click.argument("label_program", type=click.Choice(_LABEL_PROGRAM_CHOICES, case_sensitive=False))
def run_label_program(label_program: str) -> None:
    """Run the bounded canonical label-program loop."""
    from d5_trading_engine.research_loop.shadow_runner import ShadowRunner

    runner = ShadowRunner(get_settings())

    try:
        if label_program == "canonical-direction-v1":
            result = runner.run_label_program_v1()
            click.echo(
                "✓ canonical_direction_v1: "
                f"{result['run_id']} artifacts={result['artifact_dir']} "
                f"proposal={result['proposal_status']}"
            )
            return
        raise click.ClickException(f"Unsupported label program: {label_program}")
    except Exception as exc:
        click.echo(f"✗ Label program failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-strategy-eval")
@click.argument("strategy_eval", type=click.Choice(_STRATEGY_EVAL_CHOICES, case_sensitive=False))
def run_strategy_eval(strategy_eval: str) -> None:
    """Run the bounded named strategy-family challenger loop."""
    from d5_trading_engine.research_loop.shadow_runner import ShadowRunner

    runner = ShadowRunner(get_settings())

    try:
        if strategy_eval == "governed-challengers-v1":
            result = runner.run_strategy_eval_v1()
            click.echo(
                "✓ governed_challengers_v1: "
                f"{result['run_id']} artifacts={result['artifact_dir']} "
                f"top_family={result['top_family'] or 'none'} "
                f"proposal={result['proposal_status']}"
            )
            return
        raise click.ClickException(f"Unsupported strategy eval: {strategy_eval}")
    except Exception as exc:
        click.echo(f"✗ Strategy evaluation failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-paper-cycle")
@click.argument("quote_snapshot_id", type=int)
@click.option(
    "--condition-run-id",
    default=None,
    help="Optional condition run id to replay a specific regime receipt.",
)
@click.option(
    "--strategy-report",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Optional advisory strategy report JSON. Defaults to "
        ".ai/dropbox/research/STRAT-001__strategy_challenger_report.json."
    ),
)
def run_paper_cycle(
    quote_snapshot_id: int,
    condition_run_id: str | None,
    strategy_report: Path | None,
) -> None:
    """Run one bounded paper-trading cycle from advisory strategy to settlement."""
    from d5_trading_engine.paper_runtime.operator import PaperTradeOperator

    operator = PaperTradeOperator(get_settings())

    try:
        result = operator.run_cycle(
            quote_snapshot_id=quote_snapshot_id,
            strategy_report_path=strategy_report,
            condition_run_id=condition_run_id,
        )
        click.echo(
            "✓ paper_cycle: "
            f"{result['session_key']} status={result['session_status']} "
            f"filled={result['filled']} "
            f"top_family={result['strategy_selection']['top_family']} "
            f"artifacts={result['artifact_dir']}"
        )
    except Exception as exc:
        click.echo(f"✗ Paper cycle failed: {exc}", err=True)
        sys.exit(1)


@cli.command("review-proposal")
@click.argument("proposal_id")
def review_proposal(proposal_id: str) -> None:
    """Review one bounded advisory proposal and write review receipts."""
    from d5_trading_engine.research_loop.proposal_review import ProposalReviewer

    reviewer = ProposalReviewer(get_settings())

    try:
        result = reviewer.review_proposal(proposal_id)
        click.echo(
            "✓ review_proposal: "
            f"{result['proposal_id']} decision={result['decision']} "
            f"review_id={result['review_id']} artifacts={result['artifact_dir']}"
        )
    except Exception as exc:
        click.echo(f"✗ Proposal review failed: {exc}", err=True)
        sys.exit(1)


@cli.command("compare-proposals")
@click.option(
    "--proposal-id",
    "proposal_ids",
    multiple=True,
    help="Explicit proposal id to compare. Repeat to compare a bounded pool.",
)
@click.option(
    "--proposal-kind",
    default=None,
    help="Optional proposal kind filter, e.g. label_program_follow_on.",
)
@click.option(
    "--story-class",
    default=None,
    help="Optional story class filter, e.g. label_program or strategy_eval.",
)
@click.option(
    "--semantic-regime",
    default=None,
    help="Optional semantic regime filter against latest review truth.",
)
@click.option(
    "--choose-top",
    is_flag=True,
    help="Mark the highest-ranked same-scope proposal as selected_next and supersede lower-ranked same-kind competitors.",
)
def compare_proposals(
    proposal_ids: tuple[str, ...],
    proposal_kind: str | None,
    story_class: str | None,
    semantic_regime: str | None,
    choose_top: bool,
) -> None:
    """Compare reviewed proposals and optionally choose the next bounded experiment."""
    from d5_trading_engine.research_loop.proposal_comparison import ProposalComparator

    comparator = ProposalComparator(get_settings())

    try:
        result = comparator.compare_proposals(
            proposal_ids=list(proposal_ids),
            proposal_kind=proposal_kind,
            story_class=story_class,
            semantic_regime=semantic_regime,
            choose_top=choose_top,
        )
        click.echo(
            "✓ compare_proposals: "
            f"{result['comparison_id']} ranked={result['ranked_count']} "
            f"selected={result['selected_proposal_id'] or 'none'} "
            f"artifacts={result['artifact_dir']}"
        )
    except Exception as exc:
        click.echo(f"✗ Proposal comparison failed: {exc}", err=True)
        sys.exit(1)


@cli.command()
def status() -> None:
    """Show engine health — recent ingest runs and source health."""
    from sqlalchemy import func

    from d5_trading_engine.capture.lane_status import build_capture_lane_status_snapshot
    from d5_trading_engine.storage.truth.engine import get_session
    from d5_trading_engine.storage.truth.models import (
        ConditionGlobalRegimeSnapshotV1,
        ConditionScoringRun,
        IngestRun,
        SourceHealthEvent,
    )

    settings = get_settings()
    session = get_session(settings)

    try:
        lane_snapshot = build_capture_lane_status_snapshot(settings=settings)

        click.echo("=== Recent Ingest Runs ===")
        runs = session.query(IngestRun).order_by(IngestRun.created_at.desc()).limit(10).all()
        if not runs:
            click.echo("  No ingest runs yet.")
        for run in runs:
            click.echo(
                f"  {run.run_id:40s}  {run.status:8s}  "
                f"records={run.records_captured or 0:5d}  "
                f"{run.started_at}"
            )

        click.echo("\n=== Source Health ===")
        subq = (
            session.query(
                SourceHealthEvent.provider,
                func.max(SourceHealthEvent.checked_at).label("latest"),
            )
            .group_by(SourceHealthEvent.provider)
            .subquery()
        )
        events = (
            session.query(SourceHealthEvent)
            .join(
                subq,
                (SourceHealthEvent.provider == subq.c.provider)
                & (SourceHealthEvent.checked_at == subq.c.latest),
            )
            .all()
        )
        if not events:
            click.echo("  No health events yet.")
        for event in events:
            indicator = "✓" if event.is_healthy else "✗"
            click.echo(
                f"  {indicator} {event.provider:10s}  "
                f"latency={event.latency_ms:.0f}ms  "
                f"{event.endpoint}  "
                f"{event.checked_at}"
            )

        click.echo("\n=== Capture Lanes ===")
        for lane_name, lane in lane_snapshot["lanes"].items():
            eligible = "yes" if lane["downstream_eligible"] else "no"
            required = "yes" if lane["required_for_authorization"] else "no"
            click.echo(
                f"  {lane_name:22s}  state={lane['freshness_state']:14s}  "
                f"eligible={eligible:3s}  required={required:3s}  "
                f"success={lane['last_success_at_utc'] or '-'}"
            )
            click.echo(
                f"    provider={lane['provider']}  capture={lane['capture_type']}  "
                f"class={lane['expectation_class']}  "
                f"failure={lane['last_failure_at_utc'] or '-'}  "
                f"health={lane['latest_health_at_utc'] or '-'}"
            )
            if lane["latest_raw_receipt_at_utc"]:
                click.echo(f"    raw_receipt={lane['latest_raw_receipt_at_utc']}")
            if lane["latest_error_summary"]:
                click.echo(f"    error={lane['latest_error_summary']}")

        if lane_snapshot["blocking_lanes"]:
            click.echo(
                "  required blockers="
                + ", ".join(str(item) for item in lane_snapshot["blocking_lanes"])
            )
        else:
            click.echo("  required blockers=none")

        click.echo("\n=== Current Condition ===")
        latest_condition = (
            session.query(ConditionScoringRun)
            .order_by(
                ConditionScoringRun.finished_at.desc(),
                ConditionScoringRun.started_at.desc(),
            )
            .first()
        )
        if latest_condition is None:
            click.echo("  No condition runs yet.")
        else:
            finished_at = latest_condition.finished_at or latest_condition.started_at
            if latest_condition.status != "success":
                click.echo(
                    f"  latest run failed  run={latest_condition.run_id}  "
                    f"model={latest_condition.model_family}  finished={finished_at}"
                )
                if latest_condition.error_message:
                    click.echo(f"  error={latest_condition.error_message}")
                click.echo("  no current eligible snapshot from the latest run.")
            else:
                snapshot = (
                    session.query(ConditionGlobalRegimeSnapshotV1)
                    .filter_by(condition_run_id=latest_condition.run_id)
                    .order_by(ConditionGlobalRegimeSnapshotV1.created_at.desc())
                    .first()
                )
                if snapshot is None:
                    click.echo(
                        f"  latest successful run {latest_condition.run_id} has no snapshot."
                    )
                else:
                    block_indicator = "blocked" if snapshot.blocked_flag else "eligible"
                    click.echo(
                        f"  {snapshot.semantic_regime:14s} "
                        f"confidence={snapshot.confidence:.3f}  "
                        f"{block_indicator:8s}  "
                        f"{snapshot.bucket_start_utc}"
                    )
                    click.echo(
                        f"  run={latest_condition.run_id}  model={latest_condition.model_family}  "
                        f"feature_run={latest_condition.source_feature_run_id}"
                    )

        click.echo(f"\nDB: {settings.db_path}")
        click.echo(f"DuckDB: {settings.duckdb_path}")
        click.echo(f"Coinbase raw DB: {settings.coinbase_raw_db_path}")
        click.echo(f"Raw data: {settings.raw_dir}")
    finally:
        session.close()


@cli.command("sync-duckdb")
@click.argument("tables", nargs=-1)
def sync_duckdb(tables: tuple[str, ...]) -> None:
    """Sync canonical truth tables to DuckDB analytics mirror."""
    from d5_trading_engine.storage.analytics.duckdb_mirror import DuckDBMirror

    default_tables = [
        "token_registry",
        "token_metadata_snapshot",
        "token_price_snapshot",
        "quote_snapshot",
        "fred_series_registry",
        "fred_observation",
        "program_registry",
        "solana_address_registry",
        "solana_transfer_event",
        "market_instrument_registry",
        "market_candle",
        "market_trade_event",
        "order_book_l2_event",
        "ingest_run",
        "source_health_event",
        "feature_materialization_run",
        "feature_spot_chain_macro_minute_v1",
        "feature_global_regime_input_15m_v1",
        "condition_scoring_run",
        "condition_global_regime_snapshot_v1",
        "experiment_run",
        "experiment_metric",
        "artifact_reference",
        "improvement_proposal_v1",
        "proposal_review_v1",
        "proposal_comparison_v1",
        "proposal_comparison_item_v1",
        "proposal_supersession_v1",
    ]

    tables_to_sync = list(tables) if tables else default_tables
    mirror = DuckDBMirror()

    click.echo("Syncing to DuckDB analytics mirror...")
    for table in tables_to_sync:
        try:
            rows = mirror.sync_from_sqlite(table)
            click.echo(f"  ✓ {table}: {rows} rows")
        except Exception as exc:
            click.echo(f"  ✗ {table}: {exc}", err=True)

    mirror.close()
    click.echo("DuckDB sync complete.")


def main() -> None:
    """Entry point for the d5 CLI."""
    cli()


if __name__ == "__main__":
    main()
