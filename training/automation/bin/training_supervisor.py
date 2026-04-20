#!/usr/bin/env python3
"""Continuous paper-training supervisor for the repo-owned training lane.

The supervisor follows the machine-readable status contract instead of treating
the full Massive cache as an all-or-nothing gate. A partial 730-day cache should
not block the selected quickstart regimen once its required history is ready.
"""

from __future__ import annotations

import argparse
import json
import time
import traceback
from datetime import datetime, timezone
from typing import Any

from d5_trading_engine.research_loop.training_runtime import TrainingRuntime


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(event: str, **payload: Any) -> None:
    print(
        json.dumps(
            {
                "ts": _utc_now(),
                "event": event,
                **payload,
            },
            sort_keys=True,
        ),
        flush=True,
    )


def _historical_ladder_completed(status: dict[str, Any]) -> bool:
    training_status = status.get("training_status") or {}
    receipt_loop_state = training_status.get("receipt_loop_state") or {}
    if receipt_loop_state.get("historical_ladder_completed"):
        return True
    return str(training_status.get("effective_loop_status") or "") == "bootstrap_completed"


def run_supervisor(
    *,
    sleep_seconds: float,
    collect_sleep_seconds: float,
    max_massive_days: int,
    include_jupiter: bool,
    include_helius: bool,
    training_regimen: str,
) -> None:
    runtime = TrainingRuntime()
    while True:
        try:
            status = runtime.status()
            cache = status["historical_cache_status"]
            selected_profile = status.get("selected_training_profile") or {}
            ladder_complete = _historical_ladder_completed(status)
            emit(
                "status",
                run_id=status.get("run_id", ""),
                selected_training_profile=selected_profile.get("name", ""),
                selected_training_profile_ready=bool(selected_profile.get("ready")),
                historical_ladder_completed=ladder_complete,
                cache_complete=cache["complete"],
                completed_day_count=cache["completed_day_count"],
                missing_day_count=cache["missing_day_count"],
                next_missing_date=cache["next_missing_date"],
                next_command=status.get("next_command", ""),
            )

            if selected_profile.get("ready") and not ladder_complete:
                result = runtime.bootstrap(training_profile_name=training_regimen)
                bootstrap = result.get("bootstrap", {})
                backtest = bootstrap.get("backtest_result", {})
                emit(
                    "bootstrap",
                    run_id=result.get("run_id", ""),
                    training_profile_name=(
                        bootstrap.get("training_profile", {}) or {}
                    ).get("name", ""),
                    feature_run_id=bootstrap.get("feature_run_id", ""),
                    comparison_run_id=(bootstrap.get("comparison_result", {}) or {}).get(
                        "run_id",
                        "",
                    ),
                    backtest_run_id=backtest.get("run_id", ""),
                    backtest_window_count=backtest.get("window_count", 0),
                    completed_ladder=bool(bootstrap.get("completed_ladder")),
                    next_command=result.get("next_command", ""),
                )
                time.sleep(collect_sleep_seconds)
                continue

            if not selected_profile.get("ready"):
                result = runtime.hydrate_history(
                    max_days=max_massive_days,
                    training_profile_name=training_regimen,
                )
                cache_after = result.get("historical_cache_status", {})
                emit(
                    "hydrate_history",
                    run_id=result.get("run_id", ""),
                    status=result.get("status", ""),
                    selected_training_profile=selected_profile.get("name", ""),
                    completed_day_count=cache_after.get("completed_day_count", 0),
                    missing_day_count=cache_after.get("missing_day_count", 0),
                    next_command=result.get("next_command", ""),
                )
                time.sleep(collect_sleep_seconds)
                continue

            collect = runtime.collect(
                max_massive_days=max_massive_days,
                include_helius=include_helius,
                include_jupiter=include_jupiter,
            )
            emit(
                "collect",
                run_id=collect.get("run_id", ""),
                status=collect.get("status", ""),
                cache_complete=collect["historical_cache_status"]["complete"],
                next_command=collect.get("next_command", ""),
            )
            review = runtime.review()
            emit(
                "review",
                run_id=review.get("run_id", ""),
                active_profile_revision_id=review.get("active_profile_revision_id", ""),
                next_command=review.get("next_command", ""),
            )
            loop = runtime.loop(with_helius_ws=False, max_iterations=1)
            emit(
                "loop",
                run_id=loop.get("run_id", ""),
                iterations_completed=loop.get("iterations_completed", 0),
                active_profile_revision_id=loop.get("active_profile_revision_id", ""),
                latest_trade_receipt=loop.get("latest_trade_receipt", {}),
                next_command=loop.get("next_command", ""),
            )
            time.sleep(sleep_seconds)
        except KeyboardInterrupt:
            emit("stopped")
            raise
        except Exception as exc:
            emit("error", error=str(exc))
            traceback.print_exc()
            time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sleep-seconds", type=float, default=60.0)
    parser.add_argument("--collect-sleep-seconds", type=float, default=5.0)
    parser.add_argument("--max-massive-days", type=int, default=1)
    parser.add_argument("--training-regimen", default="auto")
    parser.add_argument("--include-jupiter", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--include-helius", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args()
    run_supervisor(
        sleep_seconds=args.sleep_seconds,
        collect_sleep_seconds=args.collect_sleep_seconds,
        max_massive_days=args.max_massive_days,
        include_jupiter=args.include_jupiter,
        include_helius=args.include_helius,
        training_regimen=args.training_regimen,
    )


if __name__ == "__main__":
    main()
