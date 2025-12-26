import json
import logging

import pandas as pd

from tradingview_scraper.risk import AntifragilityAuditor, TailRiskAuditor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("antifragility_audit")


def audit_portfolio_fragility():
    # 1. Load Returns
    returns = pd.read_pickle("data/lakehouse/portfolio_returns.pkl")
    with open("data/lakehouse/portfolio_meta.json", "r") as f:
        meta = json.load(f)

    # Filter valid columns
    returns = returns.loc[:, (returns != 0).any(axis=0)]

    # 2. Audit Antifragility
    auditor = AntifragilityAuditor()
    af_df = auditor.audit(returns)

    # 3. Audit Tail Risk
    tail_auditor = TailRiskAuditor()
    tail_df = tail_auditor.calculate_metrics(returns, confidence_level=0.95)

    # 4. Merge Metrics
    df = pd.merge(af_df, tail_df, on="Symbol")

    # Inject metadata
    df["Direction"] = df["Symbol"].apply(lambda x: meta.get(x, {}).get("direction", "N/A"))
    df["ADX"] = df["Symbol"].apply(lambda x: meta.get(x, {}).get("adx", 0))

    # Fragility Score (Inverse of Antifragility + High CVaR)
    # We want to identify symbols that are most prone to large left-tail losses
    df["Fragility_Score"] = (1.0 - (df["Antifragility_Score"] / df["Antifragility_Score"].max())) + (abs(df["CVaR_95"]) / abs(df["CVaR_95"]).max())

    print("\n" + "=" * 100)
    print("PORTFOLIO FRAGILITY & TAIL RISK AUDIT")
    print("=" * 100)

    print("\n[Top 10 Antifragile Candidates (Positive Skew / Convexity)]")
    print(df.sort_values("Antifragility_Score", ascending=False).head(10)[["Symbol", "Direction", "Skew", "Tail_Gain", "Antifragility_Score"]].to_string(index=False))

    print("\n[Top 10 High Tail Risk Assets (Expected Shortfall / CVaR 95%)]")
    cols = ["Symbol", "Direction", "CVaR_95", "VaR_95", "Tail_Ratio", "Max_Drawdown"]
    print(df.sort_values("CVaR_95", ascending=True).head(10)[cols].to_string(index=False))

    print("\n[Bottom 10 Most Fragile Assets (Composite Fragility Score)]")
    print(df.sort_values("Fragility_Score", ascending=False).head(10)[["Symbol", "Direction", "Fragility_Score", "CVaR_95", "Skew"]].to_string(index=False))

    # Save for Barbell Optimizer and Reporting
    df.to_json("data/lakehouse/antifragility_stats.json")
    print("\nSaved comprehensive risk stats to data/lakehouse/antifragility_stats.json")


if __name__ == "__main__":
    audit_portfolio_fragility()
