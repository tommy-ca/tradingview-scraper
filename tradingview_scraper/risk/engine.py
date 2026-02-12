from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable, List, Optional

import pandas as pd

from tradingview_scraper.risk.models import Instruction, RiskContext, RiskEvent

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
            if self.context.veto_registry.is_vetoed(str(ins.symbol)):
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
        self.ledger: Any | None = None
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

        self._entry_budget = None
        self._entry_budget_fail_closed = False
        if getattr(settings, "features", None) and getattr(settings.features, "feat_daily_risk_budget_slices", False):
            from tradingview_scraper.risk.budget import DailyRiskBudgetSlices, RiskBudgetPolicy

            self._entry_budget_fail_closed = True
            self._entry_budget = DailyRiskBudgetSlices(
                RiskBudgetPolicy(
                    total_slices_per_campaign=int(getattr(settings, "risk_budget_total_slices_per_campaign", 10)),
                    slice_pct=float(getattr(settings, "risk_budget_slice_pct", 0.005)),
                    max_entries_per_day=int(getattr(settings, "risk_budget_max_entries_per_day", 2)),
                    max_slices_per_day=int(getattr(settings, "risk_budget_max_slices_per_day", 2)),
                    max_slices_per_entry=int(getattr(settings, "risk_budget_max_slices_per_entry", 2)),
                    risk_reset_tz=str(getattr(settings, "risk_reset_tz", "UTC")),
                    risk_reset_time=str(getattr(settings, "risk_reset_time", "00:00")),
                ),
                run_dir=getattr(settings, "summaries_run_dir", None),
                fail_closed=True,
            )

    def sync_daily_state(self, equity: float, balance: float, ledger: Optional[Any] = None):
        """Called at the start of a rebalance window or daily reset."""
        self.ledger = ledger
        self.context.sync_daily_baseline(equity, ledger=ledger)
        self.context.starting_balance = balance

        if self._entry_budget is not None and ledger is not None:
            # If we previously detected any trust failure, emit a one-time audit record.
            try:
                audit_trust_failure = getattr(self._entry_budget, "audit_trust_failure", None)
                if callable(audit_trust_failure):
                    audit_trust_failure(ledger, account_id=self.context.account_id)
            except Exception as e:
                logger.error("Risk budget trust audit failed: %s", e)

            # Only rehydrate once per process (success path only).
            if getattr(self._entry_budget, "_rehydrated", False) is False:
                try:
                    self._entry_budget.rehydrate_from_ledger(ledger, account_id=self.context.account_id)
                    setattr(self._entry_budget, "_rehydrated", True)
                except Exception as e:
                    logger.critical("Risk budget rehydrate failed (fail-closed): %s", e)
                    self._append_budget_audit(
                        ledger,
                        {
                            "type": "RISK_BUDGET_REHYDRATE_FAILURE",
                            "account_id": self.context.account_id,
                            "error": repr(e),
                            "fail_closed": bool(self._entry_budget_fail_closed),
                        },
                    )

    def _append_budget_audit(self, ledger: Any, record: dict[str, Any]) -> None:
        append = getattr(ledger, "_append", None)
        if callable(append):
            append(record)
            return

        path = getattr(ledger, "path", None)
        if path is None:
            return
        try:
            import json

            with open(path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            return

    def evaluate_entry_budget(self, intent: Any) -> Any:
        """Evaluates and (if allowed) consumes daily risk budget slices.

        `intent` should be `tradingview_scraper.risk.budget.EntryIntent`.
        """
        if self._entry_budget is None:
            return None

        try:
            return self._entry_budget.evaluate_entry(intent, e_ref=float(self.context.daily_starting_equity), ledger=self.ledger)
        except Exception as e:
            logger.critical("Risk budget evaluation failed (fail-closed): %s", e)
            try:
                from tradingview_scraper.risk.budget import EntryDecision, compute_day_key

                ts_utc = getattr(intent, "ts_utc", None) or datetime.now(timezone.utc)
                day_key = compute_day_key(ts_utc, str(getattr(self.settings, "risk_reset_tz", "UTC")), str(getattr(self.settings, "risk_reset_time", "00:00")))
                if self.ledger is not None:
                    self._append_budget_audit(
                        self.ledger,
                        {
                            "type": "RISK_BUDGET_SYSTEM_BLOCK",
                            "account_id": self.context.account_id,
                            "day_key": day_key,
                            "symbol": str(getattr(intent, "symbol", "")),
                            "side": str(getattr(intent, "side", "")),
                            "reason_code": "STATE_UNTRUSTED",
                            "error": repr(e),
                        },
                    )

                return EntryDecision(
                    allow=False,
                    reason_code="STATE_UNTRUSTED",
                    entry_risk_pct=0.0,
                    required_slices=0,
                    day_key=day_key,
                    e_ref=float(self.context.daily_starting_equity),
                    campaign_slices_remaining=int(getattr(self._entry_budget.state, "campaign_slices_remaining", 0)),
                    entries_today=int(getattr(self._entry_budget.state, "entries_today", 0)),
                    slices_used_today=int(getattr(self._entry_budget.state, "slices_used_today", 0)),
                )
            except Exception:
                # Last resort: fail closed without structured decision.
                return {"allow": False, "reason_code": "STATE_UNTRUSTED"}

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
            sym_str = str(symbol)
            if self.context.veto_registry.is_vetoed(sym_str):
                # Preserve original index key to avoid dtype/index regressions.
                final_weights.loc[symbol] = 0.0

        return final_weights
