import json
import os
import sys
from datetime import datetime

import pytest

# Ensure imports work for local modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tradingview_scraper.risk.budget import DailyRiskBudgetSlices, EntryIntent, RiskBudgetPolicy, compute_day_key
from tradingview_scraper.utils.audit import AuditLedger


def _load_entry_decisions(ledger: AuditLedger) -> list[dict]:
    if not ledger.path.exists():
        return []
    records = []
    with open(ledger.path, "r") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("type") == "RISK_BUDGET_ENTRY_DECISION":
                records.append(rec)
    return records


def test_day_boundary_and_daily_caps(tmp_path):
    ledger = AuditLedger(tmp_path)
    policy = RiskBudgetPolicy(max_entries_per_day=2, max_slices_per_day=2)
    budget = DailyRiskBudgetSlices(policy, run_dir=tmp_path)

    e_ref = 100_000.0

    # Day 1
    ts1 = datetime(2026, 2, 10, 23, 0, 0)
    assert compute_day_key(ts1, "UTC", "00:00") == "2026-02-10"

    i1 = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="i1",
        ts_utc=ts1,
    )
    d1 = budget.evaluate_entry(i1, e_ref=e_ref, ledger=ledger)
    assert d1.allow is True
    assert d1.entries_today == 1

    i2 = EntryIntent(
        account_id="primary",
        symbol="BINANCE:ETHUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="i2",
        ts_utc=ts1,
    )
    d2 = budget.evaluate_entry(i2, e_ref=e_ref, ledger=ledger)
    assert d2.allow is True
    assert d2.entries_today == 2

    i3 = EntryIntent(
        account_id="primary",
        symbol="BINANCE:SOLUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="i3",
        ts_utc=ts1,
    )
    d3 = budget.evaluate_entry(i3, e_ref=e_ref, ledger=ledger)
    assert d3.allow is False
    assert d3.reason_code == "DAILY_ENTRIES_EXCEEDED"

    # Day 2 resets counters
    ts2 = datetime(2026, 2, 11, 0, 1, 0)
    i4 = EntryIntent(
        account_id="primary",
        symbol="BINANCE:XRPUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="i4",
        ts_utc=ts2,
    )
    d4 = budget.evaluate_entry(i4, e_ref=e_ref, ledger=ledger)
    assert d4.allow is True
    assert d4.entries_today == 1
    assert d4.day_key == "2026-02-11"


@pytest.mark.parametrize(
    "risk_pct, expected_slices",
    [
        (0.004999, 1),
        (0.005000, 1),
        (0.005001, 2),
        (0.009999, 2),
    ],
)
def test_slice_math_boundaries(tmp_path, risk_pct, expected_slices):
    ledger = AuditLedger(tmp_path)
    policy = RiskBudgetPolicy(slice_pct=0.005, max_slices_per_entry=2)
    budget = DailyRiskBudgetSlices(policy, run_dir=tmp_path)

    e_ref = 100_000.0
    max_loss = risk_pct * e_ref

    intent = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=10_000.0 - max_loss,
        intent_id=f"risk-{risk_pct}",
        ts_utc=datetime(2026, 2, 10, 12, 0, 0),
    )

    decision = budget.evaluate_entry(intent, e_ref=e_ref, ledger=ledger)
    assert decision.allow is True
    assert decision.required_slices == expected_slices


def test_blocks_missing_stop(tmp_path):
    ledger = AuditLedger(tmp_path)
    budget = DailyRiskBudgetSlices(RiskBudgetPolicy(), run_dir=tmp_path)

    intent = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=None,
        intent_id="no-stop",
        ts_utc=datetime(2026, 2, 10, 12, 0, 0),
    )
    decision = budget.evaluate_entry(intent, e_ref=100_000.0, ledger=ledger)
    assert decision.allow is False
    assert decision.reason_code == "MISSING_STOP"

    recs = _load_entry_decisions(ledger)
    assert len(recs) == 1
    assert recs[0]["decision"] == "BLOCK"
    assert recs[0]["reason_code"] == "MISSING_STOP"


def test_blocks_invalid_e_ref_emits_ledger(tmp_path):
    ledger = AuditLedger(tmp_path)
    budget = DailyRiskBudgetSlices(RiskBudgetPolicy(), run_dir=tmp_path)

    intent = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="bad-e-ref",
        ts_utc=datetime(2026, 2, 10, 12, 0, 0),
    )
    decision = budget.evaluate_entry(intent, e_ref=0.0, ledger=ledger)
    assert decision.allow is False
    assert decision.reason_code == "INVALID_E_REF"

    recs = _load_entry_decisions(ledger)
    assert len(recs) == 1
    assert recs[0]["decision"] == "BLOCK"
    assert recs[0]["reason_code"] == "INVALID_E_REF"


def test_blocks_invalid_prices_emits_ledger(tmp_path):
    ledger = AuditLedger(tmp_path)
    budget = DailyRiskBudgetSlices(RiskBudgetPolicy(), run_dir=tmp_path)

    intent = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=0.0,
        stop_loss_price=9_500.0,
        intent_id="bad-prices",
        ts_utc=datetime(2026, 2, 10, 12, 0, 0),
    )
    decision = budget.evaluate_entry(intent, e_ref=100_000.0, ledger=ledger)
    assert decision.allow is False
    assert decision.reason_code == "INVALID_PRICES"

    recs = _load_entry_decisions(ledger)
    assert len(recs) == 1
    assert recs[0]["decision"] == "BLOCK"
    assert recs[0]["reason_code"] == "INVALID_PRICES"


def test_restart_rehydration_no_double_spend(tmp_path):
    ledger = AuditLedger(tmp_path)
    policy = RiskBudgetPolicy(total_slices_per_campaign=3, max_entries_per_day=3, max_slices_per_day=3)

    b1 = DailyRiskBudgetSlices(policy, run_dir=tmp_path)
    e_ref = 100_000.0
    ts = datetime(2026, 2, 10, 12, 0, 0)

    i1 = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="intent-1",
        ts_utc=ts,
    )
    d1 = b1.evaluate_entry(i1, e_ref=e_ref, ledger=ledger)
    assert d1.allow is True

    # Restart
    b2 = DailyRiskBudgetSlices(policy, run_dir=tmp_path)
    b2.rehydrate_from_ledger(ledger, account_id="primary")

    # Retry same intent_id should not spend again
    d_retry = b2.evaluate_entry(i1, e_ref=e_ref, ledger=ledger)
    assert d_retry.allow is True
    assert d_retry.campaign_slices_remaining == d1.campaign_slices_remaining


def test_concurrency_only_one_consumes_capacity(tmp_path):
    ledger = AuditLedger(tmp_path)
    policy = RiskBudgetPolicy(total_slices_per_campaign=1, max_entries_per_day=1, max_slices_per_day=1)
    budget = DailyRiskBudgetSlices(policy, run_dir=tmp_path)
    e_ref = 100_000.0
    ts = datetime(2026, 2, 10, 12, 0, 0)

    intents = [
        EntryIntent(
            account_id="primary",
            symbol="BINANCE:BTCUSDT",
            side="BUY",
            quantity=1.0,
            expected_entry_price=10_000.0,
            stop_loss_price=9_500.0,
            intent_id="c1",
            ts_utc=ts,
        ),
        EntryIntent(
            account_id="primary",
            symbol="BINANCE:ETHUSDT",
            side="BUY",
            quantity=1.0,
            expected_entry_price=10_000.0,
            stop_loss_price=9_500.0,
            intent_id="c2",
            ts_utc=ts,
        ),
    ]

    import threading

    results = []
    lock = threading.Lock()

    def worker(ix: int):
        d = budget.evaluate_entry(intents[ix], e_ref=e_ref, ledger=ledger)
        with lock:
            results.append(d)

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert sum(1 for r in results if r.allow) == 1
    assert budget.state.entries_today <= 1
    assert budget.state.slices_used_today <= 1
    assert budget.state.campaign_slices_remaining in (0, 1)


def test_fail_closed_on_rehydrate_ledger_read_failure(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from tradingview_scraper.risk.engine import RiskManagementEngine

    ledger = AuditLedger(tmp_path)
    ledger.path.write_text("", encoding="utf-8")

    settings = SimpleNamespace(
        initial_capital=100000.0,
        max_daily_loss_pct=0.05,
        max_total_loss_pct=0.10,
        features=SimpleNamespace(feat_daily_risk_budget_slices=True),
        risk_budget_total_slices_per_campaign=10,
        risk_budget_slice_pct=0.005,
        risk_budget_max_entries_per_day=2,
        risk_budget_max_slices_per_day=2,
        risk_budget_max_slices_per_entry=2,
        risk_reset_tz="UTC",
        risk_reset_time="00:00",
        summaries_run_dir=tmp_path,
    )

    engine = RiskManagementEngine(settings)

    import builtins

    real_open = builtins.open

    def failing_open(path, mode="r", *args, **kwargs):
        if str(path) == str(ledger.path) and "r" in str(mode):
            raise OSError("simulated ledger read failure")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", failing_open)

    # Should not crash the pipeline; it should put the budget into a fail-closed state.
    engine.sync_daily_state(equity=100000.0, balance=100000.0, ledger=ledger)

    intent = EntryIntent(
        account_id="primary",
        symbol="BINANCE:BTCUSDT",
        side="BUY",
        quantity=1.0,
        expected_entry_price=10_000.0,
        stop_loss_price=9_500.0,
        intent_id="rehydrate-fail",
        ts_utc=datetime(2026, 2, 10, 12, 0, 0),
    )

    decision = engine.evaluate_entry_budget(intent)
    assert decision.allow is False
    assert decision.reason_code == "STATE_UNTRUSTED"

    monkeypatch.setattr(builtins, "open", real_open)

    # Audit: we should have an explicit system-block record.
    recs = [line for line in ledger.path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any('"type": "RISK_BUDGET_SYSTEM_BLOCK"' in r for r in recs)
