import json
import logging
from pathlib import Path

import pandas as pd
import yaml

from tradingview_scraper.risk import AntifragilityAuditor, TailRiskAuditor
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("antifragility_audit")


def calculate_regime_survival(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Checks if assets survived defined historical stress events.
    """
    cal_path = Path("configs/stress_calendar.yaml")
    if not cal_path.exists():
        logger.warning("Stress calendar missing. Defaulting to 100% survival.")
        return pd.DataFrame({"Symbol": returns.columns, "Regime_Survival_Score": 1.0})

    with open(cal_path, "r") as f:
        config = yaml.safe_load(f)

    events = config.get("stress_events", [])
    if not events:
        return pd.DataFrame({"Symbol": returns.columns, "Regime_Survival_Score": 1.0})

    results = []
    for symbol in returns.columns:
        passed = 0
        total_eligible = 0

        for event in events:
            start = pd.to_datetime(event["start"])
            end = pd.to_datetime(event["end"])

            # Check if the asset was even alive (first valid bar before or during event)
            if returns.index[0] > end:
                continue  # Event is before the data start

            total_eligible += 1

            # Extract event window
            mask = (returns.index >= start) & (returns.index <= end)
            window_data = returns.loc[mask, symbol]

            if window_data.empty:
                continue

            # Pass criteria: < 5% missing bars (0.0 returns)
            gap_pct = (window_data == 0).mean()
            if gap_pct < 0.05:
                passed += 1

        score = passed / total_eligible if total_eligible > 0 else 0.5  # Neutral for brand new assets
        results.append(
            {
                "Symbol": symbol,
                "Regime_Survival_Score": score,
                "Events_Tested": total_eligible,
                "Events_Passed": passed,
            }
        )

    return pd.DataFrame(results)


def audit_portfolio_fragility():
    # 1. Load Returns
    returns = pd.read_pickle("data/lakehouse/portfolio_returns.pkl")
    with open("data/lakehouse/portfolio_meta.json", "r") as f:
        meta = json.load(f)

    # Filter valid columns
    returns = returns.loc[:, (returns != 0).any(axis=0)]

    # --- GATE 1: FORENSIC HEALTH CHECK ---
    min_history = 250
    max_gap_pct = 0.05

    health_results = {}
    valid_symbols = []

    for symbol in returns.columns:
        series = returns[symbol].replace(0, pd.NA).dropna()
        n_bars = len(series)
        gap_pct = (returns[symbol] == 0).mean()

        is_healthy = n_bars >= min_history and gap_pct <= max_gap_pct
        health_results[symbol] = {"n_bars": n_bars, "gap_pct": gap_pct, "is_healthy": is_healthy}
        if is_healthy:
            valid_symbols.append(symbol)
        else:
            logger.warning(f"Symbol {symbol} FAILED Gate 1 (Health): {n_bars} bars, {gap_pct:.1%} gaps")

    # --- REGIME SURVIVAL (V3) ---
    settings = get_settings()
    if settings.features.feat_regime_survival:
        survival_df = calculate_regime_survival(returns)
        logger.info("Darwinian Audit: Regime Survival enabled.")
    else:
        survival_df = pd.DataFrame({"Symbol": returns.columns, "Regime_Survival_Score": 1.0, "Events_Tested": 0, "Events_Passed": 0})

    # 2. Audit Antifragility
    auditor = AntifragilityAuditor()
    af_df = auditor.audit(returns)

    # 3. Audit Tail Risk
    tail_auditor = TailRiskAuditor()
    tail_df = tail_auditor.calculate_metrics(returns, confidence_level=0.95)

    # 4. Merge Metrics
    df = pd.merge(af_df, tail_df, on="Symbol")
    df = pd.merge(df, survival_df, on="Symbol")

    # Inject metadata
    df["Direction"] = df["Symbol"].apply(lambda x: meta.get(x, {}).get("direction", "N/A"))
    df["ADX"] = df["Symbol"].apply(lambda x: meta.get(x, {}).get("adx", 0))

    # Inject Health Metrics
    df["Bars"] = df["Symbol"].apply(lambda x: health_results.get(x, {}).get("n_bars", 0))
    df["Gap_Pct"] = df["Symbol"].apply(lambda x: health_results.get(x, {}).get("gap_pct", 0))

    # Fragility Score (V3): Composite of Risk + Survival Failure
    if settings.features.feat_regime_survival:
        df["Fragility_Score"] = (
            (1.0 - (df["Antifragility_Score"] / df["Antifragility_Score"].max().replace(0, 1)))
            + (abs(df["CVaR_95"]) / abs(df["CVaR_95"].max().replace(0, 1)))
            + ((1.0 - df["Regime_Survival_Score"]) * 2.0)
            + (df["Gap_Pct"] * 5)
        )
    else:
        df["Fragility_Score"] = (1.0 - (df["Antifragility_Score"] / df["Antifragility_Score"].max().replace(0, 1))) + (abs(df["CVaR_95"]) / abs(df["CVaR_95"].max().replace(0, 1)))

    print("\n" + "=" * 100)
    print("PORTFOLIO FRAGILITY & DARWINIAN SURVIVAL AUDIT (V3)")
    print("=" * 100)

    print("\n[Top 10 Institutional-Grade Survivors (Regime Survival >= 0.8)]")
    cols = ["Symbol", "Direction", "Regime_Survival_Score", "Events_Passed", "Antifragility_Score"]
    print(df.sort_values(["Regime_Survival_Score", "Antifragility_Score"], ascending=False).head(10)[cols].to_string(index=False))

    print("\n[Bottom 10 Most Fragile Assets (Composite Fragility Score)]")
    print(df.sort_values("Fragility_Score", ascending=False).head(10)[["Symbol", "Direction", "Fragility_Score", "Regime_Survival_Score", "Skew"]].to_string(index=False))

    # Save for MPS Selection
    df.to_json("data/lakehouse/antifragility_stats.json")
    print("\nSaved comprehensive risk stats to data/lakehouse/antifragility_stats.json")

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
