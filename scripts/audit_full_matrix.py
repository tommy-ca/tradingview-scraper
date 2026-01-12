import json
import os
import pandas as pd
from typing import Dict, List, Any


def audit_full_matrix(run_id: str):
    log_path = f"artifacts/summaries/runs/{run_id}/audit.jsonl"
    if not os.path.exists(log_path):
        print(f"Log path not found: {log_path}")
        return

    data = []

    with open(log_path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                step = entry.get("step")
                status = entry.get("status")

                if step == "backtest_simulate" and status == "success":
                    ctx = entry.get("context", {})
                    outcome = entry.get("outcome", {})
                    metrics = outcome.get("metrics", {})

                    # We need to find the number of assets from the corresponding optimize step
                    # For simplicity, we'll just collect the Sharpe ratio here
                    data.append(
                        {
                            "window": ctx.get("window_index"),
                            "engine": ctx.get("engine"),
                            "profile": ctx.get("profile"),
                            "sharpe": metrics.get("sharpe", 0.0),
                            "ann_return": metrics.get("annualized_return", 0.0),
                            "max_dd": metrics.get("max_drawdown", 0.0),
                        }
                    )
            except Exception:
                continue

    df = pd.DataFrame(data)
    if df.empty:
        print("No simulation data found.")
        return

    # Pivot to see Profile vs Engine (Average Sharpe across all windows)
    print("\n### 📈 Average Sharpe Ratio Matrix (All Windows)")
    pivot_sharpe = df.pivot_table(index="profile", columns="engine", values="sharpe", aggfunc="mean")
    print(pivot_sharpe.to_markdown())

    print("\n### 📉 Average Max Drawdown Matrix (All Windows)")
    pivot_dd = df.pivot_table(index="profile", columns="engine", values="max_dd", aggfunc="mean")
    print(pivot_dd.to_markdown())

    # Detailed Window Matrix for 'adaptive' engine
    print("\n### 🧠 Adaptive Engine: Window-by-Window Sharpe")
    df_adaptive = df[df["engine"] == "adaptive"]
    if not df_adaptive.empty:
        pivot_window = df_adaptive.pivot_table(index="window", columns="profile", values="sharpe")
        print(pivot_window.to_markdown())


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    audit_full_matrix(args.run_id)
