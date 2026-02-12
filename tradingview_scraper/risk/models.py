from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    """
    Structured source identification for instructions and risk events.
    Avoids 'stringly-typed' ID concatenation.
    """

    run_id: str
    strategy_id: str
    regime_id: Optional[str] = None


class Instruction(BaseModel):
    """
    Atomic trading instruction emitted by the Risk Engine.
    Replaces loose weight-matrix handoffs.
    """

    symbol: str
    action: Literal["OPEN", "CLOSE", "VETO", "SCALE"]
    target_weight: float = Field(..., ge=-1.0, le=1.0)
    sl_price: Optional[float] = None
    tp_price: Optional[float] = None
    provenance: Provenance


class RiskEvent(BaseModel):
    """
    Record of a risk-triggered action (e.g., SL hit, MDD breach).
    Persisted to audit.jsonl for forensic integrity.
    """

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    trigger: str  # e.g., "DAILY_LOSS_LIMIT", "STOP_LOSS_HIT"
    symbol: Optional[str] = None
    action: Literal["VETO", "FLATTEN", "SCALE"]
    value_at_trigger: float
    threshold_violated: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VetoEntry(BaseModel):
    """
    Represents a symbol currently restricted from trading.
    """

    reason: str
    expires_at: Optional[datetime] = None
    value_at_trigger: float
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VetoRegistry(BaseModel):
    """
    State container for active trading restrictions.
    Integrated into the AllocationContext.
    """

    locked_symbols: Dict[str, VetoEntry] = Field(default_factory=dict)

    def is_vetoed(self, symbol: str) -> bool:
        entry = self.locked_symbols.get(symbol)
        if not entry:
            return False

        if entry.expires_at and datetime.now(timezone.utc) > entry.expires_at:
            # Self-healing: remove expired veto
            del self.locked_symbols[symbol]
            return False

        return True

    def add_veto(self, symbol: str, reason: str, value: float, ttl_seconds: Optional[int] = None):
        expires_at = None
        if ttl_seconds:
            from datetime import timedelta

            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

        self.locked_symbols[symbol] = VetoEntry(reason=reason, expires_at=expires_at, value_at_trigger=value)


class RiskContext(BaseModel):
    """
    Real-time state container for risk evaluation.
    Used to track daily baselines and intraday equity movements.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_id: str
    starting_balance: float
    daily_starting_equity: float  # Snapshot at 00:00 UTC
    current_equity: float
    intraday_max_equity: float = 0.0

    # State
    veto_registry: VetoRegistry = Field(default_factory=VetoRegistry)

    # Constraints
    max_daily_loss_pct: float = 0.05
    max_total_loss_pct: float = 0.10

    def sync_daily_baseline(self, current_equity: float, ledger: Optional[Any] = None):
        """
        Snapshots current equity as the daily baseline.
        If ledger is provided, attempts to recover from the last 'risk_snapshot' event (Shadow Snapshot).
        """
        recovered = False
        if ledger:
            try:
                # Mock logic: query ledger for most recent 00:00 UTC snapshot
                # In real implementation: ledger.query_latest(event="risk_snapshot", time_ge=today_00_00)
                pass
            except Exception as e:
                import logging

                logging.getLogger("risk.models").warning(f"Failed to recover risk snapshot from ledger: {e}")

        if not recovered:
            self.daily_starting_equity = current_equity
            self.intraday_max_equity = current_equity
