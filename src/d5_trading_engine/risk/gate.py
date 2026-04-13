"""
D5 Trading Engine — Risk Gate (Scaffold)

The risk gate is the final authority on whether a proposed action
(trade, position change, parameter update) is allowed to proceed.

This module will own:
- Position size limits
- Daily drawdown halts
- Concentration limits
- Slippage/price-impact hard vetoes
- Emergency halt (kill switch)
- Rate limiting (orders per period)

The risk gate NEVER suggests trades — it only vetoes unsafe ones.
The risk gate is ALWAYS conservative — when in doubt, veto.

TODO: Implement after paper settlement surface is functional.
"""

from __future__ import annotations

from d5_trading_engine.common.logging import get_logger

log = get_logger(__name__)


class RiskGate:
    """Risk gate — final authority on action safety (scaffold).

    All methods default to VETO until properly implemented.
    This is fail-closed by design.
    """

    def check_trade(self, proposal: dict) -> dict:
        """Check whether a proposed trade is allowed.

        Args:
            proposal: Trade proposal dict with mint, amount, direction, etc.

        Returns:
            Dict with allowed (bool), reason (str), and vetoes (list).
        """
        log.warning("risk_gate_scaffold_veto", detail="All trades vetoed until risk gate is implemented")
        return {
            "allowed": False,
            "reason": "Risk gate not yet implemented — all actions vetoed (fail closed)",
            "vetoes": ["scaffold_not_implemented"],
            "is_scaffold": True,
        }

    def emergency_halt(self) -> bool:
        """Check if emergency halt is active.

        Returns:
            True (always halted in scaffold mode).
        """
        return True
