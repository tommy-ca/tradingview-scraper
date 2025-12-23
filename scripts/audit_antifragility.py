import json
import logging

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("antifragility_audit")


def audit_antifragility():
    # 1. Load Returns
    returns = pd.read_pickle("data/lakehouse/portfolio_returns.pkl")
    with open("data/lakehouse/portfolio_meta.json", "r") as f:
        meta = json.load(f)

    # Filter valid columns
    returns = returns.loc[:, (returns != 0).any(axis=0)]

    stats = []

    for symbol in returns.columns:
        res = returns[symbol]

        # Calculate Antifragility Metrics
        # Skewness: Positive is 'Options-like' (Antifragile)
        # Kurtosis: High means 'Fat Tails'
        skew = res.skew()
        kurt = res.kurtosis()
        vol = res.std() * np.sqrt(252)

        # Tail Gain: Average return during top 5% of moves
        threshold = res.quantile(0.95)
        tail_gain = res[res > threshold].mean() if not res[res > threshold].empty else 0

        stats.append({"Symbol": symbol, "Direction": meta[symbol]["direction"], "Vol": vol, "Skew": skew, "Kurtosis": kurt, "Tail_Gain": tail_gain, "ADX": meta[symbol]["adx"]})

    df = pd.DataFrame(stats)

    # Antifragility Score: Favor Positive Skew and High Tail Gain
    # Normalized sum of Skew and Tail Gain
    df["Antifragility_Score"] = (df["Skew"] - df["Skew"].min()) / (df["Skew"].max() - df["Skew"].min()) + (df["Tail_Gain"] - df["Tail_Gain"].min()) / (df["Tail_Gain"].max() - df["Tail_Gain"].min())

    print("\n" + "=" * 100)
    print("ANTIFRAGILITY AUDIT (Convexity & Tail Metrics)")
    print("=" * 100)

    print("\n[Top 10 Antifragile Candidates (Positive Skew / Tail Benefit)]")
    print(df.sort_values("Antifragility_Score", ascending=False).head(10)[["Symbol", "Direction", "Skew", "Tail_Gain", "Antifragility_Score"]].to_string(index=False))

    print("\n[Bottom 10 Fragile Assets (Negative Skew / Tail Risk)]")
    print(df.sort_values("Antifragility_Score", ascending=True).head(10)[["Symbol", "Direction", "Skew", "Tail_Gain", "Antifragility_Score"]].to_string(index=False))

    # Save for Barbell Optimizer
    df.to_json("data/lakehouse/antifragility_stats.json")
    print("\nSaved stats to data/lakehouse/antifragility_stats.json")


if __name__ == "__main__":
    audit_antifragility()
