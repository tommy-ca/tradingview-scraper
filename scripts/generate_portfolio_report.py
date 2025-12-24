import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def draw_bar(weight: float, max_width: int = 15) -> str:
    """Generates a text-based progress bar."""
    filled = int(min(1.0, weight * 4) * max_width)  # scaled so 25% is full-ish
    return "[" + "█" * filled + " " * (max_width - filled) + "]"


def get_market_category(market: str) -> str:
    """Maps granular market labels to broad asset classes."""
    m = market.upper()
    if "BOND" in m:
        return "🏛️ BONDS"
    if any(x in m for x in ["BINANCE", "BITGET", "BYBIT", "OKX", "CRYPTO"]):
        return "🪙 CRYPTO"
    if any(x in m for x in ["NASDAQ", "NYSE", "AMEX", "US_STOCKS", "US_ETF"]):
        return "📈 EQUITIES"
    if any(x in m for x in ["FUTURES", "CME", "CBOT", "COMEX"]):
        return "⛓️ FUTURES"
    if "FOREX" in m:
        return "💱 FOREX"
    return "🌐 OTHER"


def calculate_portfolio_vol(assets: List[Dict[str, Any]], returns_df: Optional[pd.DataFrame]) -> float:
    """Calculates estimated annualized portfolio volatility."""
    if returns_df is None or returns_df.empty:
        return 0.0

    weights_map = {str(a["Symbol"]): float(a["Weight"]) for a in assets}
    # Align with returns columns
    common_symbols = [s for s in weights_map.keys() if s in returns_df.columns]
    if not common_symbols:
        return 0.0

    w = np.array([weights_map[s] for s in common_symbols], dtype=float)
    sub_rets = returns_df[common_symbols]

    # Simple manual variance calculation to satisfy linter
    cov = sub_rets.cov().values * 252
    port_var = float(np.matmul(w.T, np.matmul(cov, w)))
    return float(np.sqrt(port_var)) if port_var > 0 else 0.0


def generate_markdown_report(data_path: str, returns_path: str, output_path: str):
    with open(data_path, "r") as f:
        data = json.load(f)

    returns_df: Optional[pd.DataFrame] = None
    if os.path.exists(returns_path):
        try:
            raw_rets = pd.read_pickle(returns_path)
            if isinstance(raw_rets, pd.DataFrame):
                returns_df = raw_rets
        except Exception:
            pass

    profiles = data.get("profiles", {})

    md = []
    md.append("# 📊 Clustered Portfolio Analysis Report")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("\n**Quick Links:** [Deeper Cluster Analysis](./cluster_analysis.md) | [Risk Rationale](./research/antifragile_barbell_rationale.md)")
    md.append("\n---")

    for profile_name, profile_data in profiles.items():
        pretty_name = profile_name.replace("_", " ").title()
        assets = profile_data.get("assets", [])
        clusters = profile_data.get("clusters", [])

        # Calculate Stats
        vol = calculate_portfolio_vol(assets, returns_df)
        unique_clusters = len(clusters)
        top_3_conc = sum(float(c["Total_Weight"]) for c in clusters[:3]) if clusters else 0.0

        md.append(f"\n## 📈 {pretty_name} Profile")
        md.append(f"> **Strategy Metrics:** Est. Annual Vol: **{vol:.2%}** | Unique Buckets: **{unique_clusters}** | Top 3 Concentration: **{top_3_conc:.2%}**")

        # Cluster Summary Table
        md.append("\n### 🧩 Risk Bucket Allocation (Clusters)")
        md.append("| Cluster | Weight | Concentration | Lead Asset | Assets | Type | Sectors |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for cluster in clusters:
            weight = float(cluster["Total_Weight"])
            bar = draw_bar(weight)
            lead = f"`{cluster['Lead_Asset']}`"
            count = cluster["Asset_Count"]
            risk_type = cluster.get("Type", "CORE")
            sector = cluster.get("Sectors", "N/A")
            if isinstance(sector, list):
                sector = ", ".join(sector)

            md.append(f"| {cluster['Cluster_Label']} | **{weight:.2%}** | `{bar}` | {lead} | {count} | {risk_type} | {sector} |")

        # Asset Class Breakdown
        md.append("\n### 💎 Asset Class Breakdown")

        # Group assets by class
        categorized: Dict[str, List[Dict[str, Any]]] = {}
        for a in assets:
            cat = get_market_category(a.get("Market", "UNKNOWN"))
            if cat not in categorized:
                categorized[cat] = []
            categorized[cat].append(a)

        # Sort categories for consistent order
        for cat in sorted(categorized.keys()):
            md.append(f"#### {cat}")
            md.append("| Symbol | Description | Cluster | Weight | Bar | Direction |")
            md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

            cat_assets = sorted(categorized[cat], key=lambda x: x["Weight"], reverse=True)
            for asset in cat_assets:
                weight = float(asset["Weight"])
                bar = draw_bar(weight, max_width=10)
                direction = f"**{asset['Direction']}**"
                desc = asset.get("Description", "N/A")
                if desc == "N/A":
                    desc = str(asset["Symbol"]).split(":")[-1]  # fallback to ticker
                if len(desc) > 40:
                    desc = desc[:37] + "..."

                md.append(f"| `{asset['Symbol']}` | {desc} | {asset['Cluster_ID']} | {weight:.2%} | `{bar}` | {direction} |")

        md.append("\n---")

    with open(output_path, "w") as f:
        f.write("\n".join(md))

    print(f"✅ Prettified report generated at: {output_path}")


if __name__ == "__main__":
    generate_markdown_report("data/lakehouse/portfolio_optimized_v2.json", "data/lakehouse/portfolio_returns.pkl", "summaries/portfolio_report.md")
