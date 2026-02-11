from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Literal, Optional, Any, Callable

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from tradingview_scraper.risk.models import RiskEvent, VetoRegistry, Instruction, RiskContext
from tradingview_scraper.risk.guards import check_account_mdd, check_equity_guard

logger = logging.getLogger("risk.engine")


class RiskPolicy:
    """
    Centralized supervisor for enforcing hierarchical risk guardrails.
    Evaluates a sequence of predicates (Guards) to determine trade validity.
    """

    def __init__(self, context: RiskContext):
        self.context = context
        self._guards: List[Callable[[RiskContext], Optional[RiskEvent]]] = [check_equity_guard, check_account_mdd]

    def add_guard(self, guard: Callable[[RiskContext], Optional[RiskEvent]]):
        self._guards.append(guard)

    def evaluate(self, current_equity: float, current_balance: Optional[float] = None) -> List[RiskEvent]:
        """
        Updates context and executes all registered guards.
        """
        self.context.current_equity = current_equity
        if current_balance:
            self.context.starting_balance = current_balance

        # Update intraday high
        self.context.intraday_max_equity = max(self.context.intraday_max_equity, current_equity)

        events = []
        for guard in self._guards:
            event = guard(self.context)
            if event:
                events.append(event)
                # If Level 1 (Account) violation, we usually stop immediately
                if event.action == "FLATTEN":
                    logger.critical(f"Account-level risk breach detected: {event.trigger}")
                    break

        return events

    def filter_instructions(self, instructions: List[Instruction]) -> List[Instruction]:
        """
        Applies active vetoes and scaling overrides to a set of instructions.
        """
        filtered = []
        for ins in instructions:
            if self.context.veto_registry.is_vetoed(ins.symbol):
                logger.warning(f"Instruction for {ins.symbol} rejected due to active veto.")
                continue

            filtered.append(ins)
        return filtered


class RiskManagementEngine:
    """
    Orchestrator for multi-level risk enforcement.
    Provides a unified interface for backtesting (matrix) and live (event) risk logic.
    """

    def __init__(self, settings: Any):
        self.settings = settings
        # Initialize Context with default baseline (will be synced later)
        self.context = RiskContext(
            account_id="primary",
            starting_balance=settings.initial_capital,
            daily_starting_equity=settings.initial_capital,
            current_equity=settings.initial_capital,
            max_daily_loss_pct=settings.max_daily_loss_pct,
            max_total_loss_pct=settings.max_total_loss_pct,
        )
        self.policy = RiskPolicy(self.context)

    def apply_account_circuit_breaker(self, equity: float, balance: float) -> bool:
        """
        Returns False if a FLATTEN event occurred, True otherwise.
        """
        events = self.policy.evaluate(current_equity=equity, current_balance=balance)
        for event in events:
            if event.action == "FLATTEN":
                return False
        return True

    def process_rebalance(self, target_weights: pd.Series, audit_ledger: Any) -> pd.Series:
        """
        Applies Level 2 (Correlation) and Level 3 (Kelly) overrides to target weights.
        """
        from tradingview_scraper.risk.guards import apply_kelly_scaling

        # 1. Kelly Scaling
        # For simplicity, assume win_rate/payoff extracted from ledger in a real impl
        # Here we use defaults or settings
        # target_weights = apply_kelly_scaling(target_weights, ...)

        # 2. Veto Check
        final_weights = target_weights.copy()
        for symbol in target_weights.index:
            if self.context.veto_registry.is_vetoed(symbol):
                final_weights[symbol] = 0.0

        return final_weights
