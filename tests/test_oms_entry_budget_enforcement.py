from __future__ import annotations

from types import SimpleNamespace

from tradingview_scraper.execution.budget_enforcer import BudgetEnforcedExecutionEngine
from tradingview_scraper.execution.oms import OrderSide, OrderType, UnifiedAccountState, UnifiedOrderRequest, UnifiedOrderResult, UnifiedPosition
from tradingview_scraper.risk.engine import RiskManagementEngine
from tradingview_scraper.utils.audit import AuditLedger


class _StubExecutionEngine:
    def __init__(self, *, positions: list[UnifiedPosition] | None = None):
        self._positions = positions or []
        self.submitted: list[UnifiedOrderRequest] = []

    def connect(self) -> None:
        return

    def disconnect(self) -> None:
        return

    def get_account_state(self) -> UnifiedAccountState:
        return UnifiedAccountState(balance=100_000.0, equity=100_000.0)

    def get_positions(self) -> list[UnifiedPosition]:
        return list(self._positions)

    def submit_order(self, order: UnifiedOrderRequest) -> UnifiedOrderResult:
        self.submitted.append(order)
        return UnifiedOrderResult(id="stub-1", status="FILLED", filled_qty=float(order.quantity), avg_fill_price=float(order.price or 0.0))

    def close_position(self, symbol: str, quantity: float | None = None) -> UnifiedOrderResult:
        return UnifiedOrderResult(id="stub-close", status="FILLED")

    def close_all(self) -> list[UnifiedOrderResult]:
        return [UnifiedOrderResult(id="stub-close-all", status="FILLED")]


def _settings_with_budget(*, tmp_path):
    return SimpleNamespace(
        initial_capital=100_000.0,
        max_daily_loss_pct=0.05,
        max_total_loss_pct=0.10,
        risk_budget_total_slices_per_campaign=10,
        risk_budget_slice_pct=0.005,
        risk_budget_max_entries_per_day=10,
        risk_budget_max_slices_per_day=10,
        risk_budget_max_slices_per_entry=1,
        risk_reset_tz="UTC",
        risk_reset_time="00:00",
        summaries_run_dir=tmp_path,
        features=SimpleNamespace(feat_daily_risk_budget_slices=True),
    )


def test_budget_blocks_exposure_increasing_order_and_prevents_submission(tmp_path):
    ledger = AuditLedger(tmp_path)
    settings = _settings_with_budget(tmp_path=tmp_path)
    risk_engine = RiskManagementEngine(settings)
    risk_engine.sync_daily_state(equity=100_000.0, balance=100_000.0, ledger=ledger)

    stub = _StubExecutionEngine(positions=[])
    oms = BudgetEnforcedExecutionEngine(engine=stub, risk_engine=risk_engine, ledger=ledger)

    # 1% risk with max_slices_per_entry=1 @ slice_pct=0.5% => required_slices=2 => BLOCK
    order = UnifiedOrderRequest(
        symbol="BINANCE:BTCUSDT",
        side=OrderSide.BUY,
        quantity=1.0,
        type=OrderType.MARKET,
        price=10_000.0,
        stop_loss=9_000.0,
        ref_id="intent-1",
    )

    res = oms.submit_order(order)
    assert res.status == "REJECTED"
    assert "ENTRY_TOO_LARGE_FOR_DAILY_CAP" in (res.error or "")
    assert stub.submitted == []

    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert any("RISK_BUDGET_ENTRY_DECISION" in line and '"decision": "BLOCK"' in line for line in lines)
    assert any("OMS_ORDER_BLOCKED_BY_ENTRY_BUDGET" in line for line in lines)


def test_budget_is_not_applied_to_exposure_decreasing_orders(tmp_path):
    ledger = AuditLedger(tmp_path)
    settings = _settings_with_budget(tmp_path=tmp_path)
    risk_engine = RiskManagementEngine(settings)
    risk_engine.sync_daily_state(equity=100_000.0, balance=100_000.0, ledger=ledger)

    # Existing long position; SELL reduces exposure -> bypass budget even if order lacks stop.
    stub = _StubExecutionEngine(positions=[UnifiedPosition(symbol="BINANCE:BTCUSDT", side=OrderSide.BUY, quantity=1.0, avg_price=10_000.0, unrealized_pnl=0.0, ticket_id="t1")])
    oms = BudgetEnforcedExecutionEngine(engine=stub, risk_engine=risk_engine, ledger=ledger)

    order = UnifiedOrderRequest(
        symbol="BINANCE:BTCUSDT",
        side=OrderSide.SELL,
        quantity=0.25,
        type=OrderType.MARKET,
        price=None,
        stop_loss=None,
        ref_id="reduce-1",
    )

    res = oms.submit_order(order)
    assert res.status == "FILLED"
    assert len(stub.submitted) == 1

    path = tmp_path / "audit.jsonl"
    lines = path.read_text().splitlines() if path.exists() else []
    assert not any("RISK_BUDGET_ENTRY_DECISION" in line for line in lines)
