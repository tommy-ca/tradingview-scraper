from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from tradingview_scraper.execution.oms import ExecutionEngine, OrderSide, OrderType, UnifiedAccountState, UnifiedOrderRequest, UnifiedOrderResult, UnifiedPosition
from tradingview_scraper.risk.budget import EntryIntent
from tradingview_scraper.risk.engine import RiskManagementEngine

logger = logging.getLogger("execution.budget_enforcer")


def unified_order_request_to_entry_intent(
    order: UnifiedOrderRequest,
    *,
    account_id: str,
    ts_utc: Optional[datetime] = None,
) -> EntryIntent:
    expected_price = order.price
    if expected_price is None and order.type == OrderType.STOP:
        expected_price = order.stop_price

    # If expected price is missing, the budget evaluator will deterministically block with INVALID_PRICES.
    expected_entry_price = float(expected_price) if expected_price is not None else 0.0

    return EntryIntent(
        account_id=str(account_id),
        symbol=str(order.symbol),
        side="BUY" if order.side == OrderSide.BUY else "SELL",
        quantity=float(order.quantity),
        expected_entry_price=expected_entry_price,
        stop_loss_price=float(order.stop_loss) if order.stop_loss is not None else None,
        intent_id=str(order.ref_id) if order.ref_id is not None else None,
        ts_utc=ts_utc,
    )


def _signed_qty(*, side: OrderSide, qty: float) -> float:
    return float(qty) if side == OrderSide.BUY else -float(qty)


def _net_position_qty(positions: list[UnifiedPosition], *, symbol: str) -> float:
    net = 0.0
    for p in positions:
        if str(p.symbol) != str(symbol):
            continue
        net += _signed_qty(side=p.side, qty=float(p.quantity))
    return float(net)


def is_exposure_increasing_order(engine: ExecutionEngine, order: UnifiedOrderRequest) -> bool:
    try:
        positions = engine.get_positions()
    except Exception:
        # If we cannot read positions, we treat as exposure-increasing to keep enforcement authoritative.
        return True

    current = _net_position_qty(positions, symbol=str(order.symbol))
    delta = _signed_qty(side=order.side, qty=float(order.quantity))
    return abs(current + delta) > abs(current) + 1e-12


@dataclass
class BudgetEnforcedExecutionEngine(ExecutionEngine):
    """ExecutionEngine wrapper enforcing entry budget at submission boundary."""

    engine: ExecutionEngine
    risk_engine: RiskManagementEngine
    ledger: Optional[Any] = None
    account_id: Optional[str] = None

    def connect(self) -> None:
        return self.engine.connect()

    def disconnect(self) -> None:
        return self.engine.disconnect()

    def get_account_state(self) -> UnifiedAccountState:
        return self.engine.get_account_state()

    def get_positions(self) -> list[UnifiedPosition]:
        return self.engine.get_positions()

    def submit_order(self, order: UnifiedOrderRequest) -> UnifiedOrderResult:
        if not is_exposure_increasing_order(self.engine, order):
            return self.engine.submit_order(order)

        acct = self.account_id or getattr(getattr(self.risk_engine, "context", None), "account_id", None) or "primary"
        intent = unified_order_request_to_entry_intent(order, account_id=str(acct), ts_utc=datetime.now(timezone.utc))
        decision = self.risk_engine.evaluate_entry_budget(intent)

        if decision is not None and getattr(decision, "allow", True) is False:
            ledger = self.ledger or getattr(self.risk_engine, "ledger", None)
            self._append_block_audit(ledger, order=order, intent=intent, decision=decision)
            return UnifiedOrderResult(
                id="",
                status="REJECTED",
                error=(
                    "Blocked by entry budget: "
                    f"{getattr(decision, 'reason_code', 'UNKNOWN')} "
                    f"(required_slices={getattr(decision, 'required_slices', None)}, entry_risk_pct={getattr(decision, 'entry_risk_pct', None)})"
                ),
            )

        return self.engine.submit_order(order)

    def close_position(self, symbol: str, quantity: Optional[float] = None) -> UnifiedOrderResult:
        return self.engine.close_position(symbol, quantity)

    def close_all(self) -> list[UnifiedOrderResult]:
        return self.engine.close_all()

    def _append_block_audit(self, ledger: Optional[Any], *, order: UnifiedOrderRequest, intent: EntryIntent, decision: Any) -> None:
        if ledger is None:
            logger.warning("Entry budget BLOCK with no ledger attached: symbol=%s ref_id=%s", order.symbol, order.ref_id)
            return

        rec = {
            "type": "OMS_ORDER_BLOCKED_BY_ENTRY_BUDGET",
            "account_id": str(intent.account_id),
            "symbol": str(order.symbol),
            "side": str(order.side.value),
            "quantity": float(order.quantity),
            "order_type": str(order.type.value),
            "expected_entry_price": float(intent.expected_entry_price),
            "stop_loss_price": float(intent.stop_loss_price) if intent.stop_loss_price is not None else None,
            "ref_id": str(order.ref_id) if order.ref_id is not None else None,
            "budget": {
                "decision": "BLOCK",
                "reason_code": getattr(decision, "reason_code", None),
                "required_slices": getattr(decision, "required_slices", None),
                "entry_risk_pct": getattr(decision, "entry_risk_pct", None),
                "day_key": getattr(decision, "day_key", None),
                "e_ref": getattr(decision, "e_ref", None),
            },
        }

        append = getattr(ledger, "_append", None)
        if callable(append):
            append(rec)
            return

        # Best-effort fallback for non-AuditLedger implementations.
        try:
            path = getattr(ledger, "path", None)
            if path is None:
                return
            import json

            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception:
            return
