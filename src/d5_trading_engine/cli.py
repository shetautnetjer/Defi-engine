"""
D5 Trading Engine — CLI Entry Point

Commands:
- d5 init         : Apply Alembic migrations to head
- d5 capture      : Run data capture for one or all providers
- d5 training ... : Repo-owned training wrappers for bootstrap, walk-forward, review, loop, status, evidence, and batches
- d5 diagnose ... : Explain training-window coverage, gate funnels, and no-trade windows
- d5 hydrate-history : Hydrate a selected Massive-backed training-regimen window
- d5 training hydrate-history : Fill selected-regimen history or the missing full historical window
- d5 training collect : Incrementally append Massive/Coinbase/Jupiter/Helius source data without repulling cached history
- d5 materialize-features : Materialize deterministic feature tables
- d5 score-conditions : Score bounded market conditions
- d5 run-shadow   : Run shadow ML evaluation lanes
- d5 run-live-regime-cycle : Refresh live intraday training inputs and emit a paper-ready receipt
- d5 run-label-program : Run canonical label-program scoring
- d5 run-strategy-eval : Run governed strategy challenger scoring
- d5 run-paper-cycle : Run one bounded paper-trading cycle
- d5 run-paper-close : Close one open paper session from an explicit exit quote
- d5 run-paper-practice-bootstrap : Build the bounded historical practice ladder
- d5 run-backtest-walk-forward : Replay the adaptive historical ladder over 3-month windows
- d5 run-paper-practice-loop : Run the autonomous paper-only practice loop
- d5 paper-practice-status : Show the active paper-practice profile and loop state
- d5 live-readiness : Evaluate the governed micro-live promotion gate
- d5 micro-live ... : Arm, pause, inspect, or execute the gated Jupiter micro-live seam
- d5 compare-proposals : Rank reviewed proposals and optionally choose the next bounded experiment
- d5 capture massive-minute-aggs --date YYYY-MM-DD : Replay one historical Massive day
- d5 capture massive-minute-aggs --from YYYY-MM-DD --to YYYY-MM-DD : Replay a bounded Massive history range
- d5 capture massive-minute-aggs --full-free-tier : Replay the bounded two-year Massive free-tier window
- d5 status       : Show engine health and ingest run stats
- d5 sync-duckdb  : Sync canonical truth tables to DuckDB mirror
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path

import click
import orjson

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
_TRAINING_REGIMEN_CHOICES = [
    "auto",
    "quickstart_300d",
    "full_730d",
]


def _emit_cli_result(payload: dict[str, object], *, json_output: bool, text: str) -> None:
    """Render one CLI result in either machine or human form."""

    if json_output:
        click.echo(orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode())
        return
    click.echo(text)


def _resolve_async_result(result_or_awaitable):
    """Allow async command owners to be monkeypatched with sync fakes in tests."""

    if inspect.isawaitable(result_or_awaitable):
        return asyncio.run(result_or_awaitable)
    return result_or_awaitable


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


@cli.group("training")
def training_group() -> None:
    """Repo-owned training wrappers for automation-friendly paper practice."""


@training_group.command("bootstrap")
@click.option(
    "--training-regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default=None,
    help="Optional paper-practice history regimen for bootstrap hydration.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def training_bootstrap(training_regimen: str | None, json_output: bool) -> None:
    """Run the repo-owned historical bootstrap wrapper."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = (
            runtime.bootstrap(training_profile_name=training_regimen)
            if training_regimen
            else runtime.bootstrap()
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training bootstrap: "
                f"{result['run_id']} revision={result['active_profile_revision_id']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training bootstrap failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("hydrate-history")
@click.option(
    "--training-regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default=None,
    help="Optional history regimen to hydrate instead of the full free-tier missing window.",
)
@click.option("--max-days", type=int, default=None)
@click.option("--json", "json_output", is_flag=True, default=False)
def training_hydrate_history(
    training_regimen: str | None,
    max_days: int | None,
    json_output: bool,
) -> None:
    """Fill only the missing portion of the cached historical Massive window."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.hydrate_history(
            max_days=max_days,
            training_profile_name=training_regimen,
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training hydrate-history: "
                f"{result['run_id']} cache_complete={result['historical_cache_status']['complete']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training hydrate-history failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("collect")
@click.option("--max-massive-days", type=int, default=1)
@click.option("--include-helius/--no-include-helius", default=False)
@click.option("--include-jupiter/--no-include-jupiter", default=True)
@click.option("--json", "json_output", is_flag=True, default=False)
def training_collect(
    max_massive_days: int,
    include_helius: bool,
    include_jupiter: bool,
    json_output: bool,
) -> None:
    """Incrementally append source data without repulling the cached historical backbone."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.collect(
            max_massive_days=max_massive_days,
            include_helius=include_helius,
            include_jupiter=include_jupiter,
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training collect: "
                f"{result['run_id']} cache_complete={result['historical_cache_status']['complete']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training collect failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("walk-forward")
@click.option(
    "--training-regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default=None,
    help="Optional paper-practice history regimen for walk-forward replay.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def training_walk_forward(training_regimen: str | None, json_output: bool) -> None:
    """Run the repo-owned adaptive historical walk-forward wrapper."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = (
            runtime.walk_forward(training_profile_name=training_regimen)
            if training_regimen
            else runtime.walk_forward()
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training walk-forward: "
                f"{result['run_id']} revision={result['active_profile_revision_id']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training walk-forward failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("review")
@click.option("--json", "json_output", is_flag=True, default=False)
def training_review(json_output: bool) -> None:
    """Render the latest bounded training review packet."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.review()
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training review: "
                f"{result['run_id']} revision={result['active_profile_revision_id']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training review failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("loop")
@click.option(
    "--with-helius-ws",
    is_flag=True,
    default=False,
    help="Include one bounded Helius websocket burst in each live regime cycle.",
)
@click.option("--max-iterations", type=int, default=None)
@click.option("--json", "json_output", is_flag=True, default=False)
def training_loop(
    with_helius_ws: bool,
    max_iterations: int | None,
    json_output: bool,
) -> None:
    """Run the repo-owned training loop wrapper."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.loop(
            with_helius_ws=with_helius_ws,
            max_iterations=max_iterations,
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training loop: "
                f"{result['run_id']} iterations={result['iterations_completed']} "
                f"revision={result['active_profile_revision_id']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training loop failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("status")
@click.option("--json", "json_output", is_flag=True, default=False)
def training_status(json_output: bool) -> None:
    """Show the repo-owned training surface status."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.status()
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training status: "
                f"revision={result['active_profile_revision_id']} "
                f"workspace={result['workspace_root']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training status failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("evidence-gap")
@click.option("--json", "json_output", is_flag=True, default=False)
def training_evidence_gap(json_output: bool) -> None:
    """Rank learning gaps from paper decisions and recommend the next experiment batch."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.evidence_gap()
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training evidence-gap: "
                f"{result['run_id']} selected_batch={result['selected_batch_type']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training evidence-gap failed: {exc}", err=True)
        sys.exit(1)


@training_group.command("experiment-batch")
@click.option("--json", "json_output", is_flag=True, default=False)
def training_experiment_batch(json_output: bool) -> None:
    """Generate candidate-overlay experiment proposals from the current evidence gap."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.experiment_batch()
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ training experiment-batch: "
                f"{result['run_id']} selected_batch={result['selected_batch_type']} "
                f"candidates={result['candidate_count']} artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training experiment-batch failed: {exc}", err=True)
        sys.exit(1)


@cli.group("diagnose")
def diagnose_group() -> None:
    """Explain data coverage and paper decision-funnel failures."""


@diagnose_group.command("training-window")
@click.option(
    "--regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default="quickstart_300d",
    help="Training regimen to evaluate.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def diagnose_training_window(regimen: str, json_output: bool) -> None:
    """Summarize SQL and feature coverage for a training regimen."""
    from d5_trading_engine.runtime.diagnostics import diagnose_training_window

    try:
        result = diagnose_training_window(get_settings(), regimen=regimen)
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ diagnose training-window: "
                f"regimen={result['regimen']} status={result['status']} "
                f"sql_days={result['sql_days_present']} "
                f"feature_days={result['feature_days_present']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Training-window diagnostic failed: {exc}", err=True)
        sys.exit(1)


@diagnose_group.command("gate-funnel")
@click.option("--run", default="latest", help="Paper-practice loop run id or latest.")
@click.option("--json", "json_output", is_flag=True, default=False)
def diagnose_gate_funnel(run: str, json_output: bool) -> None:
    """Summarize how decisions moved through condition, policy, risk, and fill gates."""
    from d5_trading_engine.runtime.diagnostics import diagnose_gate_funnel

    try:
        result = diagnose_gate_funnel(get_settings(), run=run)
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ diagnose gate-funnel: "
                f"run={result['loop_run_id']} cycles={result['cycles']} "
                f"paper_filled={result['paper_filled']} "
                f"primary={result['primary_failure_surface']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Gate-funnel diagnostic failed: {exc}", err=True)
        sys.exit(1)


@diagnose_group.command("no-trades")
@click.option("--run", default="latest", help="Paper-practice loop run id or latest.")
@click.option("--window", default="300d", help="Lookback window such as 300d.")
@click.option("--json", "json_output", is_flag=True, default=False)
def diagnose_no_trades(run: str, window: str, json_output: bool) -> None:
    """Explain why a paper/training window produced no or few paper trades."""
    from d5_trading_engine.runtime.diagnostics import diagnose_no_trades

    try:
        result = diagnose_no_trades(get_settings(), run=run, window=window)
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ diagnose no-trades: "
                f"run={result['loop_run_id']} window={result['window_days']}d "
                f"paper_trades={result['paper_trades']} "
                f"primary={result['primary_failure_surface']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ No-trades diagnostic failed: {exc}", err=True)
        sys.exit(1)


@cli.command("live-readiness")
@click.option(
    "--metrics-path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
    help="Optional readiness metrics JSON path. Defaults to data/research/training/live_readiness/latest_metrics.json.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def live_readiness(metrics_path: Path | None, json_output: bool) -> None:
    """Evaluate whether paper evidence is eligible for micro-live arming."""
    from d5_trading_engine.live_execution.readiness import LiveReadinessService

    result = LiveReadinessService(get_settings()).evaluate(metrics_path=metrics_path)
    status = "passed" if result["passed"] else "failed"
    _emit_cli_result(
        result,
        json_output=json_output,
        text=f"micro-live readiness {status}: reasons={result['reason_codes']}",
    )


@cli.group("micro-live")
def micro_live_group() -> None:
    """Guarded Jupiter micro-live controls."""


@micro_live_group.command("arm")
@click.option("--max-notional-usdc", type=float, required=True)
@click.option("--daily-loss-limit-usdc", type=float, required=True)
@click.option("--weekly-loss-limit-usdc", type=float, required=True)
@click.option("--ttl-minutes", type=int, default=60, show_default=True)
@click.option("--json", "json_output", is_flag=True, default=False)
def micro_live_arm(
    max_notional_usdc: float,
    daily_loss_limit_usdc: float,
    weekly_loss_limit_usdc: float,
    ttl_minutes: int,
    json_output: bool,
) -> None:
    """Write an expiring arm state only if live-readiness currently passes."""
    from d5_trading_engine.live_execution.arm_state import MicroLiveArmStore
    from d5_trading_engine.live_execution.readiness import LiveReadinessService

    settings = get_settings()
    readiness = LiveReadinessService(settings).evaluate()
    result = MicroLiveArmStore(settings).arm(
        readiness=readiness,
        max_notional_usdc=max_notional_usdc,
        daily_loss_limit_usdc=daily_loss_limit_usdc,
        weekly_loss_limit_usdc=weekly_loss_limit_usdc,
        ttl_minutes=ttl_minutes,
    )
    status = "armed" if result["armed"] else "blocked"
    _emit_cli_result(
        result,
        json_output=json_output,
        text=f"micro-live arm {status}: reasons={result['reason_codes']}",
    )


@micro_live_group.command("status")
@click.option("--json", "json_output", is_flag=True, default=False)
def micro_live_status(json_output: bool) -> None:
    """Show current micro-live arm state."""
    from d5_trading_engine.live_execution.arm_state import MicroLiveArmStore

    result = MicroLiveArmStore(get_settings()).status()
    status = "armed" if result.get("armed") else result.get("status", "blocked")
    _emit_cli_result(
        result,
        json_output=json_output,
        text=f"micro-live status {status}: reasons={result.get('reason_codes', [])}",
    )


@micro_live_group.command("pause")
@click.option("--reason", default="operator_pause", show_default=True)
@click.option("--json", "json_output", is_flag=True, default=False)
def micro_live_pause(reason: str, json_output: bool) -> None:
    """Pause micro-live execution by clearing the arm state."""
    from d5_trading_engine.live_execution.arm_state import MicroLiveArmStore

    result = MicroLiveArmStore(get_settings()).pause(reason=reason)
    _emit_cli_result(
        result,
        json_output=json_output,
        text=f"micro-live paused: reasons={result['reason_codes']}",
    )


@micro_live_group.command("execute")
@click.option("--input-mint", required=True)
@click.option("--output-mint", required=True)
@click.option("--amount", type=int, required=True, help="Input amount in base units.")
@click.option("--slippage-bps", type=int, default=50, show_default=True)
@click.option("--json", "json_output", is_flag=True, default=False)
def micro_live_execute(
    input_mint: str,
    output_mint: str,
    amount: int,
    slippage_bps: int,
    json_output: bool,
) -> None:
    """Attempt one gated Jupiter micro-live swap.

    This command fails closed unless readiness, explicit arming, and external
    signing are all configured and passing.
    """
    from d5_trading_engine.live_execution.jupiter_micro import JupiterMicroLiveExecutor

    result = asyncio.run(
        JupiterMicroLiveExecutor(settings=get_settings()).execute_swap(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=slippage_bps,
        ),
    )
    _emit_cli_result(
        result,
        json_output=json_output,
        text=f"micro-live execute {result['status']}: reasons={result.get('reason_codes', [])}",
    )


@cli.command("hydrate-history")
@click.option(
    "--training-regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default="auto",
    show_default=True,
    help="Paper-practice history regimen to hydrate.",
)
@click.option("--max-days", type=int, default=None)
@click.option("--json", "json_output", is_flag=True, default=False)
def hydrate_history(
    training_regimen: str,
    max_days: int | None,
    json_output: bool,
) -> None:
    """Hydrate a bounded Massive history window for the selected training regimen."""
    from d5_trading_engine.research_loop.training_runtime import TrainingRuntime

    runtime = TrainingRuntime(get_settings())

    try:
        result = runtime.hydrate_history(
            max_days=max_days,
            training_profile_name=training_regimen,
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ hydrate-history: "
                f"{result['run_id']} regimen={training_regimen} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Hydrate history failed: {exc}", err=True)
        sys.exit(1)


@cli.command()
@click.argument("provider", type=click.Choice(_CAPTURE_CHOICES, case_sensitive=False))
@click.option(
    "--date",
    "date_str",
    default=None,
    help="Optional UTC date for historical flat-file capture, in YYYY-MM-DD format.",
)
@click.option("--from", "from_date", default=None, help="Inclusive UTC start date for range replay.")
@click.option("--to", "to_date", default=None, help="Inclusive UTC end date for range replay.")
@click.option(
    "--full-free-tier",
    is_flag=True,
    default=False,
    help="Replay the bounded two-year Massive crypto free-tier history window.",
)
@click.option(
    "--resume/--no-resume",
    default=True,
    help="Skip historical Massive days that already have raw files and normalized SQL rows.",
)
def capture(
    provider: str,
    date_str: str | None,
    from_date: str | None,
    to_date: str | None,
    full_free_tier: bool,
    resume: bool,
) -> None:
    """Run data capture for a specific provider or all."""
    from d5_trading_engine.capture.massive_backfill import MassiveMinuteAggsBackfill
    from d5_trading_engine.capture.runner import CaptureRunner

    settings = get_settings()
    runner = CaptureRunner(settings)
    backfill_runner = MassiveMinuteAggsBackfill(settings, runner=runner)

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

            if provider == "massive-minute-aggs":
                mode_count = int(bool(date_str)) + int(bool(from_date or to_date)) + int(bool(full_free_tier))
                if mode_count != 1:
                    raise click.ClickException(
                        "Choose exactly one Massive history mode: --date, --from/--to, or --full-free-tier."
                    )
                if date_str:
                    run_id = await runner.capture_massive_minute_aggs(date_str)
                    runner.write_capture_receipts(
                        run_id,
                        context={"requested_provider": provider, "date": date_str},
                    )
                    click.echo(f"  ✓ Massive minute aggs: {run_id}")
                elif full_free_tier:
                    payload = await backfill_runner.backfill_full_free_tier(resume=resume)
                    click.echo(
                        "  ✓ Massive minute aggs backfill: "
                        f"{payload['batch_id']} captured={payload['days']['captured_count']} "
                        f"skipped={payload['days']['skipped_count']}"
                    )
                else:
                    if not from_date or not to_date:
                        raise click.ClickException("--from and --to are both required for range replay.")
                    payload = await backfill_runner.backfill_range(
                        start_date=from_date,
                        end_date=to_date,
                        resume=resume,
                    )
                    click.echo(
                        "  ✓ Massive minute aggs backfill: "
                        f"{payload['batch_id']} captured={payload['days']['captured_count']} "
                        f"skipped={payload['days']['skipped_count']}"
                    )
            elif provider == "all" and date_str:
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
@click.option("--json", "json_output", is_flag=True, default=False)
def materialize_features(feature_set: str, json_output: bool) -> None:
    """Materialize a deterministic feature set from canonical truth."""
    from d5_trading_engine.features.materializer import FeatureMaterializer

    materializer = FeatureMaterializer(get_settings())

    try:
        if feature_set == "global-regime-inputs-15m-v1":
            run_id, row_count = materializer.materialize_global_regime_inputs_15m_v1()
            _emit_cli_result(
                {
                    "status": "completed",
                    "feature_set": "global_regime_inputs_15m_v1",
                    "feature_run_id": run_id,
                    "row_count": row_count,
                },
                json_output=json_output,
                text=f"✓ global_regime_inputs_15m_v1: {run_id} rows={row_count}",
            )
            return
        if feature_set == "spot-chain-macro-v1":
            run_id, row_count = materializer.materialize_spot_chain_macro_v1()
            _emit_cli_result(
                {
                    "status": "completed",
                    "feature_set": "spot_chain_macro_v1",
                    "feature_run_id": run_id,
                    "row_count": row_count,
                },
                json_output=json_output,
                text=f"✓ spot_chain_macro_v1: {run_id} rows={row_count}",
            )
            return
        raise click.ClickException(f"Unsupported feature set: {feature_set}")
    except Exception as exc:
        click.echo(f"✗ Feature materialization failed: {exc}", err=True)
        sys.exit(1)


@cli.command("score-conditions")
@click.argument("condition_set", type=click.Choice(_CONDITION_SET_CHOICES, case_sensitive=False))
@click.option("--json", "json_output", is_flag=True, default=False)
def score_conditions(condition_set: str, json_output: bool) -> None:
    """Score a bounded condition set from deterministic feature inputs."""
    from d5_trading_engine.condition.scorer import ConditionScorer

    scorer = ConditionScorer(get_settings())

    try:
        if condition_set == "global-regime-v1":
            result = scorer.score_global_regime_v1()
            latest = result["latest_snapshot"]
            _emit_cli_result(
                result,
                json_output=json_output,
                text=(
                    "✓ global_regime_v1: "
                    f"{result['run_id']} regime={latest['semantic_regime']} "
                    f"confidence={latest['confidence']:.3f} model={result['model_family']}"
                ),
            )
            return
        raise click.ClickException(f"Unsupported condition set: {condition_set}")
    except Exception as exc:
        click.echo(f"✗ Condition scoring failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-shadow")
@click.argument("shadow_run", type=click.Choice(_SHADOW_RUN_CHOICES, case_sensitive=False))
@click.option("--history-start", default=None, help="Inclusive UTC start date for bounded shadow history.")
@click.option("--history-end", default=None, help="Inclusive UTC end date for bounded shadow history.")
@click.option(
    "--use-massive-context/--no-use-massive-context",
    default=True,
    help="Keep or filter out Massive-backed feature buckets during the shadow comparison.",
)
@click.option(
    "--refit-cadence-buckets",
    default=None,
    type=int,
    help=(
        "Optional refit cadence for walk-forward shadow regime comparison. "
        "Defaults to REGIME_COMPARE_REFIT_CADENCE_BUCKETS."
    ),
)
@click.option("--json", "json_output", is_flag=True, default=False)
def run_shadow(
    shadow_run: str,
    history_start: str | None,
    history_end: str | None,
    use_massive_context: bool,
    refit_cadence_buckets: int | None,
    json_output: bool,
) -> None:
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
            _emit_cli_result(
                result,
                json_output=json_output,
                text=(
                    "✓ intraday_meta_stack_v1: "
                    f"{result['run_id']} artifacts={result['artifact_dir']} "
                    f"chronos={result['chronos_status']}"
                ),
            )
            return
        if shadow_run == "regime-model-compare-v1":
            result = comparator.run_regime_model_compare_v1(
                history_start=history_start,
                history_end=history_end,
                use_massive_context=use_massive_context,
                refit_cadence_buckets=refit_cadence_buckets,
            )
            _emit_cli_result(
                result,
                json_output=json_output,
                text=(
                    "✓ regime_model_compare_v1: "
                    f"{result['run_id']} artifacts={result['artifact_dir']} "
                    f"recommended={result['recommended_candidate']} "
                    f"proposal={result['proposal_status']}"
                ),
            )
            return
        raise click.ClickException(f"Unsupported shadow run: {shadow_run}")
    except Exception as exc:
        click.echo(f"✗ Shadow run failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-live-regime-cycle")
@click.option(
    "--with-helius-ws",
    is_flag=True,
    default=False,
    help="Include one bounded Helius websocket burst in the live intraday training cycle.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def run_live_regime_cycle(with_helius_ws: bool, json_output: bool) -> None:
    """Refresh live intraday inputs and emit a paper-ready receipt without auto-trading."""
    from d5_trading_engine.research_loop.live_regime_cycle import LiveRegimeCycleRunner

    runner = LiveRegimeCycleRunner(get_settings())

    try:
        result = _resolve_async_result(
            runner.run_live_regime_cycle(with_helius_ws=with_helius_ws)
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ live_regime_cycle: "
                f"{result['cycle_id']} quote_snapshot={result['quote_snapshot_id']} "
                f"ready_for_paper_cycle={result['ready_for_paper_cycle']} "
                f"proposal={result['proposal_status']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Live regime cycle failed: {exc}", err=True)
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
@click.option("--json", "json_output", is_flag=True, default=False)
def run_strategy_eval(strategy_eval: str, json_output: bool) -> None:
    """Run the bounded named strategy-family challenger loop."""
    from d5_trading_engine.research_loop.shadow_runner import ShadowRunner

    runner = ShadowRunner(get_settings())

    try:
        if strategy_eval == "governed-challengers-v1":
            result = runner.run_strategy_eval_v1()
            _emit_cli_result(
                result,
                json_output=json_output,
                text=(
                    "✓ governed_challengers_v1: "
                    f"{result['run_id']} artifacts={result['artifact_dir']} "
                    f"top_family={result['top_family'] or 'none'} "
                    f"proposal={result['proposal_status']}"
                ),
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
@click.option("--json", "json_output", is_flag=True, default=False)
def run_paper_cycle(
    quote_snapshot_id: int,
    condition_run_id: str | None,
    strategy_report: Path | None,
    json_output: bool,
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
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ paper_cycle: "
                f"{result['session_key']} status={result['session_status']} "
                f"filled={result['filled']} "
                f"top_family={result['strategy_selection']['top_family']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Paper cycle failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-paper-close")
@click.argument("session_key")
@click.option("--quote-snapshot-id", required=True, type=int)
@click.option("--reason", "close_reason", required=True)
@click.option(
    "--condition-run-id",
    default=None,
    help="Optional condition run id to replay a specific close-time regime receipt.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def run_paper_close(
    session_key: str,
    quote_snapshot_id: int,
    close_reason: str,
    condition_run_id: str | None,
    json_output: bool,
) -> None:
    """Close one open paper session from an explicit exit quote."""
    from d5_trading_engine.paper_runtime.operator import PaperTradeOperator

    operator = PaperTradeOperator(get_settings())

    try:
        result = operator.close_cycle(
            session_key=session_key,
            quote_snapshot_id=quote_snapshot_id,
            close_reason=close_reason,
            condition_run_id=condition_run_id,
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ paper_close: "
                f"{result['session_key']} status={result['settlement_result']['session_status']} "
                f"realized_pnl_usdc={result['settlement_result']['realized_pnl_usdc']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Paper close failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-paper-practice-bootstrap")
@click.option(
    "--training-regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default=None,
    help="Optional paper-practice history regimen for bootstrap hydration.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def run_paper_practice_bootstrap(training_regimen: str | None, json_output: bool) -> None:
    """Run the bounded historical bootstrap for autonomous paper practice."""
    from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime

    runtime = PaperPracticeRuntime(get_settings())

    try:
        result = (
            runtime.run_bootstrap(training_profile_name=training_regimen)
            if training_regimen
            else runtime.run_bootstrap()
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ paper_practice_bootstrap: "
                f"{result['bootstrap_id']} profile={result['profile_id']} "
                f"feature_run={result['feature_run_id']} "
                f"comparison={result['comparison_result']['run_id']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Paper practice bootstrap failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-backtest-walk-forward")
@click.option(
    "--training-regimen",
    type=click.Choice(_TRAINING_REGIMEN_CHOICES, case_sensitive=False),
    default=None,
    help="Optional paper-practice history regimen for walk-forward replay.",
)
@click.option("--json", "json_output", is_flag=True, default=False)
def run_backtest_walk_forward(training_regimen: str | None, json_output: bool) -> None:
    """Run the adaptive historical walk-forward replay ladder."""
    from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime

    runtime = PaperPracticeRuntime(get_settings())

    try:
        result = (
            runtime.run_backtest_walk_forward(training_profile_name=training_regimen)
            if training_regimen
            else runtime.run_backtest_walk_forward()
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ backtest_walk_forward: "
                f"{result['run_id']} status={result['status']} "
                f"windows={result['window_count']} "
                f"artifacts={result['artifact_dir']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Backtest walk-forward failed: {exc}", err=True)
        sys.exit(1)


@cli.command("run-paper-practice-loop")
@click.option(
    "--with-helius-ws",
    is_flag=True,
    default=False,
    help="Include one bounded Helius websocket burst in each live regime cycle.",
)
@click.option("--max-iterations", type=int, default=None)
@click.option("--json", "json_output", is_flag=True, default=False)
def run_paper_practice_loop(
    with_helius_ws: bool,
    max_iterations: int | None,
    json_output: bool,
) -> None:
    """Run the autonomous paper-only practice loop."""
    from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime

    runtime = PaperPracticeRuntime(get_settings())

    try:
        result = runtime.run_loop(
            with_helius_ws=with_helius_ws,
            max_iterations=max_iterations,
        )
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ paper_practice_loop: "
                f"{result['loop_run_id']} status={result['status']} "
                f"iterations={result['iterations_completed']} "
                f"profile={result['active_profile_id']}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Paper practice loop failed: {exc}", err=True)
        sys.exit(1)


@cli.command("paper-practice-status")
@click.option("--json", "json_output", is_flag=True, default=False)
def paper_practice_status(json_output: bool) -> None:
    """Show the active paper-practice profile and latest loop state."""
    from d5_trading_engine.paper_runtime.practice import PaperPracticeRuntime

    runtime = PaperPracticeRuntime(get_settings())

    try:
        result = runtime.get_status()
        _emit_cli_result(
            result,
            json_output=json_output,
            text=(
                "✓ paper_practice_status: "
                f"profile={result['active_profile_id']} "
                f"revision={result['active_revision_id']} "
                f"open_session={result['open_session_key'] or 'none'} "
                f"loop_status={result['latest_loop_status'] or 'none'}"
            ),
        )
    except Exception as exc:
        click.echo(f"✗ Paper practice status failed: {exc}", err=True)
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
        "paper_practice_profile_v1",
        "paper_practice_profile_revision_v1",
        "paper_practice_loop_run_v1",
        "paper_practice_decision_v1",
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
