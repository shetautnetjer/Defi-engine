"""Expiring operator arm state for micro-live execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import orjson

from d5_trading_engine.config.settings import Settings


class MicroLiveArmStore:
    """Persist an explicit, expiring micro-live arm state outside runtime code."""

    def __init__(self, settings: Settings, state_path: Path | None = None) -> None:
        self.settings = settings
        self.state_path = state_path or (
            settings.repo_root / ".ai" / "live" / "micro_live_arm_state.json"
        )

    def arm(
        self,
        *,
        readiness: dict[str, Any],
        max_notional_usdc: float,
        daily_loss_limit_usdc: float,
        weekly_loss_limit_usdc: float,
        ttl_minutes: int = 60,
    ) -> dict[str, Any]:
        """Write an armed state only after live-readiness passes."""

        if not readiness.get("passed"):
            return {
                "armed": False,
                "status": "blocked",
                "reason_codes": ["live_readiness_not_passed"],
                "readiness": readiness,
            }

        armed_at = datetime.now(UTC)
        expires_at = armed_at + timedelta(minutes=ttl_minutes)
        state = {
            "armed": True,
            "status": "armed",
            "reason_codes": [],
            "armed_at_utc": armed_at.isoformat(),
            "expires_at_utc": expires_at.isoformat(),
            "max_notional_usdc": float(max_notional_usdc),
            "daily_loss_limit_usdc": float(daily_loss_limit_usdc),
            "weekly_loss_limit_usdc": float(weekly_loss_limit_usdc),
            "ttl_minutes": int(ttl_minutes),
            "readiness_evaluated_at_utc": readiness.get("evaluated_at_utc"),
        }
        self._write_state(state)
        return state

    def pause(self, reason: str = "operator_pause") -> dict[str, Any]:
        state = {
            "armed": False,
            "status": "paused",
            "reason_codes": [reason],
            "paused_at_utc": datetime.now(UTC).isoformat(),
        }
        self._write_state(state)
        return state

    def status(self, now: datetime | None = None) -> dict[str, Any]:
        current_time = now or datetime.now(UTC)
        if not self.state_path.exists():
            return {
                "armed": False,
                "status": "not_armed",
                "reason_codes": ["micro_live_not_armed"],
            }

        state = orjson.loads(self.state_path.read_bytes())
        if not state.get("armed"):
            return state

        expires_at = datetime.fromisoformat(state["expires_at_utc"])
        if current_time > expires_at:
            expired_state = dict(state)
            expired_state["armed"] = False
            expired_state["status"] = "expired"
            expired_state["reason_codes"] = ["micro_live_arm_expired"]
            return expired_state
        return state

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_bytes(orjson.dumps(state, option=orjson.OPT_INDENT_2))

