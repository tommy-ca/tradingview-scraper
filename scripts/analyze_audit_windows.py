import argparse
import json
import os

import pandas as pd


def analyze(log_path):
    data = []

    if not os.path.exists(log_path):
        print(f"Log path not found: {log_path}")
        return

    with open(log_path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get("step") == "backtest_simulate" and entry.get("status") == "success":
                    ctx = entry.get("context", {})
                    outcome = entry.get("outcome", {}).get("metrics", {})

                    data.append({"window": ctx.get("window_index"), "profile": ctx.get("profile"), "engine": ctx.get("engine"), "sharpe": outcome.get("sharpe")})
            except Exception:
                continue

    df = pd.DataFrame(data)
    if df.empty:
        print("No backtest data found")
        return

    # Pivot to see Profile vs Window
    pivot = df.pivot_table(index="window", columns=["engine", "profile"], values="sharpe", aggfunc="mean")
    print(pivot.to_markdown())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-path", help="Path to audit.jsonl")
    args = parser.parse_args()

    path = args.log_path or "artifacts/summaries/runs/20260109-175648/audit.jsonl"
    analyze(path)
