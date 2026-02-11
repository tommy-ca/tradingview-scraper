import pandas as pd
import numpy as np
from datetime import datetime
from tradingview_scraper.risk.engine import RiskContext, RiskPolicy
from tradingview_scraper.risk.guards import check_account_mdd, check_cluster_caps, apply_kelly_scaling


def test_risk_engine():
    # 1. Setup Context
    ctx = RiskContext(account_id="test_acc", starting_balance=100000.0, daily_starting_equity=100000.0, current_equity=100000.0)
    policy = RiskPolicy(ctx)

    # 2. Test MDD Breach
    print("Testing MDD breach...")
    ctx.current_equity = 94000.0  # 6% loss
    events = policy.evaluate(current_equity=94000.0)
    assert len(events) > 0
    assert events[0].trigger == "MAX_DAILY_DRAWDOWN"
    assert events[0].action == "FLATTEN"
    print("✓ MDD breach detected.")

    # 3. Test Cluster Caps
    print("Testing cluster caps...")
    weights = {"BTC": 0.2, "ETH": 0.1, "SOL": 0.05}
    clusters = {"1": ["BTC", "ETH"], "2": ["SOL"]}
    events = check_cluster_caps(ctx, weights, clusters, cap=0.25)
    assert len(events) == 1
    assert events[0].trigger == "CLUSTER_CAP_BREACH"
    assert events[0].metadata["cluster_id"] == "1"
    print("✓ Cluster cap breach detected (BTC+ETH=0.3 > 0.25).")

    # 4. Test Kelly Scaling
    print("Testing Kelly scaling...")
    w = pd.Series([0.1, 0.2], index=["A", "B"])
    # Win rate 50%, Payoff 2:1 -> Kelly = 0.5 - 0.5/2 = 0.25
    # Fractional Kelly (0.1) = 0.025
    scaled = apply_kelly_scaling(w, win_rate=0.5, payoff_ratio=2.0, fraction=0.1)
    np.testing.assert_allclose(scaled.values, w.values * 0.025)
    print("✓ Kelly scaling correctly applied.")


if __name__ == "__main__":
    test_risk_engine()
