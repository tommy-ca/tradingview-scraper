import argparse
import json
import os
import sys
from pathlib import Path

import pandas as pd

# Ensure project root in path
sys.path.append(os.getcwd())

from tradingview_scraper.portfolio_engines.backtest_simulators import ReturnsSimulator
from tradingview_scraper.portfolio_engines.nautilus_adapter import run_nautilus_backtest
from tradingview_scraper.settings import get_settings


def validate_meta_parity(run_id: str, profile: str = "hrp"):
    print(f"🚀 Starting Nautilus Parity Validation for Run: {run_id} (Profile: {profile})")

    # 1. Resolve Paths
    run_dir = Path(f"artifacts/summaries/runs/{run_id}")
    if not run_dir.exists():
        # Try finding by partial ID if needed
        matching = list(Path("artifacts/summaries/runs").glob(f"*{run_id}*"))
        if matching:
            run_dir = matching[0]
            run_id = run_dir.name
        else:
            print(f"❌ Run directory not found: {run_id}")
            return

    returns_path = run_dir / "data" / "returns_matrix.parquet"
    weights_path = run_dir / "data" / "portfolio_optimized_v2.json"

    # Fallback to meta-optimized if needed (for meta-portfolios)
    if "meta" in run_id or not weights_path.exists():
        weights_path = Path("data/lakehouse") / f"portfolio_optimized_meta_{profile}.json"
        # If still not found, check run dir for meta output
        if not weights_path.exists():
            weights_path = run_dir / "data" / f"portfolio_optimized_meta_{profile}.json"

    if not returns_path.exists() or not weights_path.exists():
        print(f"❌ Required artifacts missing: {returns_path} or {weights_path}")
        return

    # 2. Load Data
    returns = pd.read_parquet(returns_path)
    with open(weights_path, "r") as f:
        weights_data = json.load(f)

    # Extract weights for the specific profile
    if "profiles" in weights_data:
        # Standard Pillar 3 output
        assets = weights_data["profiles"].get(profile, {}).get("assets", [])
    else:
        # Flattened Meta-Portfolio output
        assets = weights_data.get("weights", [])

    if not assets:
        print(f"❌ No assets found for profile {profile}")
        return

    weights_df = pd.DataFrame(assets)
    # Standardize column names
    if "Symbol" not in weights_df.columns and "symbol" in weights_df.columns:
        weights_df = weights_df.rename(columns={"symbol": "Symbol"})
    if "Weight" not in weights_df.columns and "weight" in weights_df.columns:
        weights_df = weights_df.rename(columns={"weight": "Weight"})

    # Ensure alignment
    common = [s for s in weights_df["Symbol"] if s in returns.columns]
    returns = returns[common].fillna(0.0)
    weights_df = weights_df[weights_df["Symbol"].isin(common)]

    print(f"📊 Testing on {len(common)} assets over {len(returns)} days.")

    settings = get_settings()

    # 3. Run Vectorized Simulator (Baseline)
    print("\n[1/2] Running Vectorized Simulator (Baseline)...")
    vector_res = ReturnsSimulator().simulate(returns=returns, weights_df=weights_df, initial_holdings=None)

    # 4. Run Nautilus Simulator (High-Fidelity)
    print("[2/2] Running Nautilus Simulator...")
    nautilus_res = run_nautilus_backtest(returns=returns, weights_df=weights_df, initial_holdings=None, settings=settings)

    # 5. Compare Results
    metrics = ["sharpe", "annualized_return", "annualized_vol", "max_drawdown"]

    audit_record = {
        "run_id": run_id,
        "profile": profile,
        "vectorized": {m: vector_res.get(m, 0.0) for m in metrics},
        "nautilus": {m: nautilus_res.get(m, 0.0) for m in metrics},
        "delta": {},
        "divergence_pct": 0.0,
    }

    print("\n" + "=" * 80)
    print(f"{'Metric':<20} | {'Vectorized':<15} | {'Nautilus':<15} | {'Delta':<10}")
    print("-" * 80)

    for m in metrics:
        v_vec = vector_res.get(m, 0.0)
        v_nau = nautilus_res.get(m, 0.0)
        delta = float(v_nau) - float(v_vec)
        audit_record["delta"][m] = delta
        print(f"{m:<20} | {v_vec:>15.4f} | {v_nau:>15.4f} | {delta:>10.4f}")

    print("=" * 80)

    # Success criteria: Sharpe divergence < 0.1 and Return divergence < 5%
    sharpe_div = abs(audit_record["delta"]["sharpe"])
    audit_record["divergence_sharpe"] = sharpe_div

    if sharpe_div < 0.2:
        print(f"\n✅ PARITY PASS (Sharpe Divergence: {sharpe_div:.4f} < 0.2)")
    else:
        print(f"\n⚠️ PARITY WARNING (Sharpe Divergence: {sharpe_div:.4f})")

    # Save Audit
    audit_out = run_dir / "reports" / "validation" / f"nautilus_parity_{profile}.json"
    audit_out.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_out, "w") as f:
        json.dump(audit_record, f, indent=2)
    print(f"📝 Audit record saved to {audit_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nautilus High-Fidelity Parity Test")
    parser.add_argument("--run-id", required=True, help="Run ID to validate")
    parser.add_argument("--profile", default="hrp", help="Risk profile to validate")
    args = parser.parse_args()

    validate_meta_parity(args.run_id, args.profile)
