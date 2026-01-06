import pandas as pd

from tradingview_scraper.portfolio_engines.backtest_simulators import ReturnsSimulator
from tradingview_scraper.portfolio_engines.nautilus_adapter import run_nautilus_backtest
from tradingview_scraper.settings import get_settings


def validate_parity():
    print("🚀 Starting Nautilus Parity Validation...")

    # 1. Load Data
    returns_path = "data/lakehouse/portfolio_returns.pkl"
    try:
        import pickle

        with open(returns_path, "rb") as f:
            returns = pickle.load(f)
    except Exception as e:
        print(f"❌ Failed to load returns: {e}")
        return

    # Take a slice for faster testing (last 60 days)
    returns = returns.tail(60).fillna(0.0)

    # 2. Define Weights (Equal Weight of Top 5 assets)
    symbols = list(returns.columns[:5])
    returns = returns[symbols]

    # Use 0.1 weight to leave plenty of cash buffer
    weights_df = pd.DataFrame({"Symbol": symbols, "Weight": [0.1] * len(symbols)})

    print(f"📊 Testing on {len(symbols)} assets over {len(returns)} days.")
    print(f"Universe: {symbols}")

    settings = get_settings()

    # 3. Run Vectorized Simulator (Baseline)
    print("\n[1/2] Running Vectorized Simulator (Baseline)...")
    legacy_res = ReturnsSimulator().simulate(returns=returns, weights_df=weights_df, initial_holdings=None)

    # 4. Run Nautilus Simulator (New Engine)
    print("[2/2] Running Nautilus Simulator...")
    nautilus_res = run_nautilus_backtest(returns=returns, weights_df=weights_df, initial_holdings=None, settings=settings)

    # 5. Compare Results
    metrics = ["sharpe", "total_return", "drawdown", "turnover"]

    import json
    import os

    os.makedirs("artifacts/audit", exist_ok=True)
    audit_record = {"legacy": {m: legacy_res.get(m, 0.0) for m in metrics}, "nautilus": {m: nautilus_res.get(m, 0.0) for m in metrics}, "delta": {}, "pass": False}

    print("\n" + "=" * 50)
    print(f"{'Metric':<15} | {'Legacy':<10} | {'Nautilus':<10} | {'Delta':<10}")
    print("-" * 50)

    for m in metrics:
        v_leg = legacy_res.get(m, 0.0)
        v_nau = nautilus_res.get(m, 0.0)
        delta = v_nau - v_leg
        audit_record["delta"][m] = delta
        print(f"{m:<15} | {v_leg:>10.4f} | {v_nau:>10.4f} | {delta:>10.4f}")

    print("=" * 50)

    # Check parity gate
    divergence = abs(nautilus_res.get("total_return", 0.0) - legacy_res.get("total_return", 0.0))
    audit_record["divergence"] = divergence

    nautilus_return = nautilus_res.get("total_return", 0.0)

    if pd.isna(nautilus_return) or abs(nautilus_return) < 1e-6:
        audit_record["pass"] = False
        print(f"\n⚠️ PARITY FAIL: Nautilus return is invalid ({nautilus_return})")
    elif divergence < 0.015:
        audit_record["pass"] = True
        print(f"\n✅ PARITY PASS (Divergence: {divergence:.4f} < 0.015)")
    else:
        audit_record["pass"] = False
        print(f"\n⚠️ PARITY AUDIT (Divergence: {divergence:.4f})")

    with open("artifacts/audit/parity_audit.json", "w") as f:
        json.dump(audit_record, f, indent=2)
    print("📝 Audit record saved to artifacts/audit/parity_audit.json")


if __name__ == "__main__":
    validate_parity()
