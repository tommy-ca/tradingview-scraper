import json
import logging
import os
from typing import Any, Dict, List, cast

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("cluster_analysis")


def analyze_clusters(clusters_path: str, meta_path: str, returns_path: str, output_path: str):
    if not os.path.exists(clusters_path) or not os.path.exists(meta_path) or not os.path.exists(returns_path):
        logger.error("Required files missing for cluster analysis.")
        return

    with open(clusters_path, "r") as f:
        clusters = cast(Dict[str, List[str]], json.load(f))
    with open(meta_path, "r") as f:
        meta = cast(Dict[str, Any], json.load(f))
    returns_raw = pd.read_pickle(returns_path)
    if not isinstance(returns_raw, pd.DataFrame):
        returns = pd.DataFrame(returns_raw)
    else:
        returns = returns_raw

    report = []
    report.append("# 🧩 Hierarchical Cluster Analysis")
    report.append(f"**Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"**Total Clusters:** {len(clusters)}")
    report.append("\n---")

    summary_data = []

    for c_id, symbols in clusters.items():
        valid_symbols = [s for s in symbols if s in returns.columns]
        if not valid_symbols:
            continue

        sub_rets = returns[valid_symbols]

        # Calculate cluster stats
        cluster_corr = sub_rets.corr()
        if len(valid_symbols) > 1:
            # Extract upper triangle of correlation matrix excluding diagonal
            corr_values = cluster_corr.values[np.triu_indices_from(cluster_corr.values, k=1)]
            avg_corr = float(np.mean(corr_values))
        else:
            avg_corr = 1.0

        mean_rets = sub_rets.mean(axis=1)
        std_val = mean_rets.std()
        # Use np.isnan for scalar check
        cluster_vol = float(std_val * np.sqrt(252)) if not np.isnan(std_val) else 0.0

        # Sector distribution
        sectors = [meta.get(s, {}).get("sector", "N/A") for s in valid_symbols]
        sector_series = pd.Series(sectors)
        sector_counts = sector_series.value_counts()
        primary_sector = str(sector_counts.index[0])
        sector_homogeneity = float(sector_counts.iloc[0]) / len(valid_symbols)

        markets = list(set(meta.get(s, {}).get("market", "UNKNOWN") for s in valid_symbols))

        report.append(f"\n## 📦 Cluster {c_id}: {primary_sector}")
        if c_id == "5":
            report.append("**Detailed Sub-Cluster Analysis:** [subcluster_5.md](./subcluster_5.md)")
        report.append(f"- **Size:** {len(valid_symbols)} assets")
        report.append(f"- **Avg Intra-Cluster Correlation:** {avg_corr:.4f}")
        report.append(f"- **Cluster Annualized Vol:** {cluster_vol:.2%}")
        report.append(f"- **Sector Homogeneity:** {sector_homogeneity:.1%}")
        report.append(f"- **Markets:** {', '.join(markets)}")

        report.append("\n### 📋 Members")
        report.append("| Symbol | Description | Sector | Market |")
        report.append("| :--- | :--- | :--- | :--- |")
        for s in valid_symbols:
            s_meta = meta.get(s, {})
            report.append(f"| `{s}` | {s_meta.get('description', 'N/A')} | {s_meta.get('sector', 'N/A')} | {s_meta.get('market', 'UNKNOWN')} |")

        summary_data.append({"Cluster": c_id, "Sector": primary_sector, "Assets": len(valid_symbols), "Avg_Corr": avg_corr, "Vol": cluster_vol, "Homogeneity": sector_homogeneity})

    # Summary Table
    report.insert(4, "\n## 📊 Clusters Overview")
    report.insert(5, "| Cluster | Primary Sector | Assets | Avg Corr | Vol | Homogeneity |")
    report.insert(6, "| :--- | :--- | :--- | :--- | :--- | :--- |")

    # Sort summary data by number of assets descending
    summary_data.sort(key=lambda x: x["Assets"], reverse=True)

    for i, s in enumerate(summary_data):
        report.insert(7 + i, f"| {s['Cluster']} | {s['Sector']} | {s['Assets']} | {s['Avg_Corr']:.3f} | {s['Vol']:.2%} | {s['Homogeneity']:.1%} |")

    with open(output_path, "w") as f:
        f.write("\n".join(report))

    logger.info(f"✅ Hierarchical cluster analysis report generated at: {output_path}")


if __name__ == "__main__":
    analyze_clusters("data/lakehouse/portfolio_clusters.json", "data/lakehouse/portfolio_meta.json", "data/lakehouse/portfolio_returns.pkl", "summaries/cluster_analysis.md")
