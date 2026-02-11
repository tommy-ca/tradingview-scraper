from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tradingview_scraper.risk.models import Instruction, RiskContext, RiskEvent, VetoRegistry

logger = logging.getLogger("risk.engine")


class RiskPolicy:
    """
    Centralized supervisor for enforcing risk guardrails.
    Evaluates a sequence of predicates (Guards) to determine trade validity.
    (Pillar 3: Risk Compliance).
    """

    def __init__(self, context: RiskContext):
        self.context = context
        # Ordered list of guards: Level 1 (Account) -> Level 2 (Cluster) -> Level 3 (Tactical)
        from tradingview_scraper.risk.guards import check_account_mdd, check_equity_guard

        self._guards: List[Callable[[RiskContext], Optional[RiskEvent]]] = [check_equity_guard, check_account_mdd]

    def add_guard(self, guard: Callable[[RiskContext], Optional[RiskEvent]]):
        """Allows dynamic injection of strategy-specific guards."""
        self._guards.append(guard)

    def evaluate(self, current_equity: float, current_balance: Optional[float] = None) -> List[RiskEvent]:
        """
        Updates context and executes all registered guards in sequence.
        Returns a list of events if any violations occurred.
        """
        self.context.current_equity = current_equity
        if current_balance:
            self.context.starting_balance = current_balance

        # Update intraday high for trailing DD logic
        self.context.intraday_max_equity = max(self.context.intraday_max_equity, current_equity)

        events = []
        for guard in self._guards:
            event = guard(self.context)
            if event:
                events.append(event)
                # Fail-Fast: If an account-level circuit breaker triggers, stop evaluating
                if event.action == "FLATTEN":
                    logger.critical(f"RISK BREACH: {event.trigger} threshold hit. Initiating shutdown.")
                    break

        return events

    def filter_instructions(self, instructions: List[Instruction]) -> List[Instruction]:
        """
        Applies active vetoes and scaling overrides to a set of instructions.
        Ensures the 'Re-entry Paradox' is avoided by checking the VetoRegistry.
        """
        filtered = []
        for ins in instructions:
            if self.context.veto_registry.is_vetoed(ins.symbol):
                logger.warning(f"VETO: Instruction for {ins.symbol} rejected due to active risk lock.")
                continue

            # Apply any tactical scaling (e.g. Kelly overrides)
            # In V2, 'SCALE' action would be handled here
            filtered.append(ins)

        return filtered


class RiskManagementEngine:
    """
    Orchestrator for multi-level risk enforcement.
    Provides a unified interface for backtesting (matrix) and live (event) risk logic.
    """

    def __init__(self, settings: Any):
        self.settings = settings
        # Initialize Context with default baseline from settings
        self.context = RiskContext(
            account_id="primary",
            starting_balance=settings.initial_capital,
            daily_starting_equity=settings.initial_capital,
            current_equity=settings.initial_capital,
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_total_loss_pct=settings.max_total_loss_pct,
        )
        self.policy = RiskPolicy(self.context)

    def sync_daily_state(self, equity: float, balance: float, ledger: Optional[Any] = None):
        """Called at the start of a rebalance window or daily reset."""
        self.context.sync_daily_baseline(equity, ledger=ledger)
        self.context.starting_balance = balance

    def process_rebalance(self, target_weights: pd.Series, audit_ledger: Optional[Any] = None) -> pd.Series:
        """
        Applies Level 2 (Correlation) and Level 3 (Kelly) overrides to target weights.
        Returns the risk-adjusted weight vector.
        """
        # 1. Level 2: Cluster Caps (Simplified integration)
        # Note: In a full implementation, this would query Pillar 1 cluster data from the context
        final_weights = target_weights.copy()

        # 2. Level 3: Tactical Scaling & Vetoes
        for symbol in target_weights.index:
            if self.context.veto_registry.is_vetoed(symbol):
                final_weights[symbol] = 0.0

        return final_weights
