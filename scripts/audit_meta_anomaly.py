import json
from pathlib import Path

import numpy as np
import pandas as pd

from tradingview_scraper.utils.metrics import calculate_performance_metrics


def audit_meta_anomaly():
    run_dir = Path("artifacts/summaries/runs/20260116-140519/data")
    profile = "max_sharpe"

    returns_path = run_dir / f"meta_returns_{profile}.pkl"
    weights_path = run_dir / f"meta_optimized_{profile}.json"

    print(f"Auditing Profile: {profile}")

    # 1. Load Returns
    if not returns_path.exists():
        print(f"Returns file missing: {returns_path}")
        return

    df = pd.read_pickle(returns_path)
    print(f"Returns Shape: {df.shape}")
    print("Returns Head:")
    print(df.head())
    print("\nReturns Stats:")
    print(df.describe())

    # Check for NaNs or Infinity
    print(f"\nNaN count: {df.isna().sum().sum()}")
    print(f"Inf count: {np.isinf(df).sum().sum()}")

    # 2. Load Weights
    if not weights_path.exists():
        print(f"Weights file missing: {weights_path}")
        return

    with open(weights_path, "r") as f:
        w_data = json.load(f)

    weights = w_data.get("weights", [])
    print(f"\nWeights Count: {len(weights)}")
    print(json.dumps(weights, indent=2))

    # 3. Reconstruct Portfolio Returns
    w_map = {item["Symbol"]: item["Weight"] for item in weights}

    # Align
    cols = [c for c in df.columns if c in w_map]
    w_vec = np.array([w_map[c] for c in cols])

    print(f"\nAligned Columns: {cols}")
    print(f"Weight Vector: {w_vec}")
    print(f"Sum Weights: {w_vec.sum()}")

    port_rets = (df[cols] * w_vec).sum(axis=1)

    print("\nPortfolio Returns Stats:")
    print(port_rets.describe())

    # 4. Calculate Metrics manually
    mean_ret = port_rets.mean()
    std_ret = port_rets.std()

    ann_ret = mean_ret * 252
    ann_vol = std_ret * np.sqrt(252)

    print(f"\nManual Annualized Return: {ann_ret:.4f} ({ann_ret * 100:.2f}%)")
    print(f"Manual Annualized Vol: {ann_vol:.4f} ({ann_vol * 100:.2f}%)")

    # 5. Compare with utils
    metrics = calculate_performance_metrics(port_rets)
    print("\nUtils Metrics:")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    audit_meta_anomaly()
