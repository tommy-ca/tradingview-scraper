import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

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
    if any(x in m for x in ["FUTURES", "CME", "CBOT", "COMEX", "NYMEX"]):
        return "⛓️ FUTURES"
    if "FOREX" in m:
        return "💱 FOREX"
    if "OANDA" in m or "UNKNOWN" in m:
        return "⛓️ COMMODITIES / CFD"
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
    sub_rets = cast(pd.DataFrame, returns_df[common_symbols])

    # Pre-calculate covariance to avoid linter confusion with chain calls
    cov_matrix = sub_rets.cov()
    annual_cov = cov_matrix.values * 252

    # Portfolio variance: w^T * Cov * w
    port_var = float(np.dot(w.T, np.dot(annual_cov, w)))
    return float(np.sqrt(port_var)) if port_var > 0 else 0.0


def generate_markdown_report(data_path: str, returns_path: str, candidates_path: str, output_path: str):
    with open(data_path, "r") as f:
        data = json.load(f)

    candidates = []
    if os.path.exists(candidates_path):
        with open(candidates_path, "r") as f:
            candidates = json.load(f)

    returns_df: Optional[pd.DataFrame] = None
    if os.path.exists(returns_path):
        try:
            raw_rets = pd.read_pickle(returns_path)
            if isinstance(raw_rets, pd.DataFrame):
                returns_df = raw_rets
        except Exception:
            pass

    profiles = data.get("profiles", {})
    cluster_registry = data.get("cluster_registry", {})

    md = []
    md.append("# 📊 Quantitative Portfolio Analysis Dashboard")
    md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("\n**Quick Links:** [Risk Rationale](./research/antifragile_barbell_rationale.md) | [Cluster Hierarchy](./cluster_analysis.md)")
    md.append("\n---")

    # 1. SHARED CLUSTER REFERENCE
    md.append("## 🧩 Shared Cluster Reference")
    md.append("Hierarchical clustering groups correlated assets into risk units to prevent over-concentration.")
    md.append("| Cluster | Primary Sector | Size | Lead Asset | Primary Markets |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")

    for c_id, c_info in sorted(cluster_registry.items(), key=lambda x: int(x[0])):
        syms = c_info.get("symbols", [])
        raw_markets = sorted(c_info.get("markets", []))
        # Truncate markets if too many
        if len(raw_markets) > 2:
            markets = ", ".join(raw_markets[:2]) + f" (+{len(raw_markets) - 2})"
        else:
            markets = ", ".join(raw_markets)

        sector = c_info.get("primary_sector", "N/A")
        # Find lead asset from first in list
        lead = syms[0] if syms else "N/A"
        md.append(f"| **Cluster {c_id}** | {sector} | {len(syms)} | `{lead}` | {markets} |")

    md.append("\n---")

    # 2. RISK PROFILES
    for profile_name, profile_data in profiles.items():
        pretty_name = profile_name.replace("_", " ").title()
        assets = profile_data.get("assets", [])
        clusters = profile_data.get("clusters", [])

        # Calculate Stats
        vol = calculate_portfolio_vol(assets, returns_df)
        unique_clusters = len(clusters)
        top_3_conc = sum(float(c["Total_Weight"]) for c in clusters[:3]) if clusters else 0.0

        # Sector Diversity Score: Count unique sectors in top 80% weight
        sorted_assets = sorted(assets, key=lambda x: x["Weight"], reverse=True)
        running_w = 0.0
        top_sectors = set()
        for a in sorted_assets:
            top_sectors.add(a.get("Sector", "N/A"))
            running_w += a["Weight"]
            if running_w >= 0.80:
                break
        sector_diversity = len(top_sectors)

        md.append(f"\n## 📈 {pretty_name} Profile")
        md.append(
            f"> **Strategy Metrics:** Est. Annual Vol: **{vol:.2%}** | Unique Buckets: **{unique_clusters}** | Sector Diversity: **{sector_diversity}** | Top 3 Concentration: **{top_3_conc:.2%}**"
        )

        # Cluster Summary Table
        md.append("\n### 🧩 Risk Bucket Allocation (Clusters)")
        md.append("| Cluster | Weight | Concentration | Lead Asset | Assets | Type | Sectors |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for cluster in clusters:
            weight = float(cluster["Total_Weight"])
            if weight < 0.001:
                continue
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
            if a["Weight"] < 0.001:
                continue  # Filter implementation noise
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

    # 3. CANDIDATE UNIVERSE
    if candidates:
        md.append("\n## 🔍 Trend Filtered Candidate Universe")
        md.append("High-liquidity symbols passing multi-timeframe technical filters.")
        md.append("| Symbol | Market | Direction | ADX | ATR% | Trend |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        sorted_candidates = sorted(candidates, key=lambda x: (get_market_category(x.get("market", "")), -x.get("adx", 0)))

        for c in sorted_candidates:
            adx = float(c.get("adx", 0))
            close = float(c.get("close", 0))
            atr = float(c.get("atr", 0))
            atr_pct = f"{(atr / close) * 100:.2f}%" if close > 0 else "N/A"

            # Simple trend strength indicator
            trend_icon = "🔥" if adx > 25 else "📈" if adx > 15 else "➡️"
            market_cat = get_market_category(c.get("market", "UNKNOWN")).split(" ")[0]  # Just emoji

            md.append(f"| `{c['symbol']}` | {market_cat} | **{c.get('direction', 'LONG')}** | {adx:.1f} | {atr_pct} | {trend_icon} |")

    with open(output_path, "w") as f:
        f.write("\n".join(md))

    print(f"✅ Prettified report generated at: {output_path}")


if __name__ == "__main__":
    generate_markdown_report("data/lakehouse/portfolio_optimized_v2.json", "data/lakehouse/portfolio_returns.pkl", "data/lakehouse/portfolio_candidates.json", "summaries/portfolio_report.md")
