import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.settings import get_settings


def generate_meta_markdown_report(meta_optimized_path: str, meta_returns_path: str, output_path: str):
    if not os.path.exists(meta_optimized_path):
        print(f"Error: {meta_optimized_path} not found.")
        return

    with open(meta_optimized_path, "r") as f:
        meta_data = json.load(f)

    returns_df = None
    if os.path.exists(meta_returns_path):
        returns_df = pd.read_pickle(meta_returns_path)

    md = []
    md.append("# 🌐 Multi-Sleeve Meta-Portfolio Report")
    md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Run ID:** {meta_data.get('metadata', {}).get('run_id', 'N/A')}")
    md.append("\n---")

    # 1. SLEEVE ALLOCATION
    md.append("## 🧩 Sleeve Allocation (Meta-HRP)")
    md.append("Top-level allocation across strategy sleeves using Hierarchical Risk Parity.")
    md.append("| Sleeve ID | Weight | Engine | Source Run |")
    md.append("| :--- | :--- | :--- | :--- |")

    weights = sorted(meta_data.get("weights", []), key=lambda x: x["Weight"], reverse=True)
    for w in weights:
        s_id = w["Symbol"]
        weight = w["Weight"]
        md.append(f"| **{s_id}** | {weight:.2%} | Custom HRP | {meta_data['metadata'].get('run_id', 'N/A')} |")

    # 2. SLEEVE CORRELATIONS
    if returns_df is not None:
        md.append("\n## 📊 Sleeve Correlations")
        corr = returns_df.corr()
        md.append("| Sleeve | " + " | ".join(corr.columns) + " |")
        md.append("| :--- | " + " | ".join([":---:"] * len(corr.columns)) + " |")
        for i, row in corr.iterrows():
            md.append(f"| **{i}** | " + " | ".join([f"{v:.2f}" for v in row]) + " |")

    # 3. FINAL ASSET TOP 20
    md.append("\n## 💎 Consolidated Top 20 Assets")
    md.append("Aggregated weights across all sleeves after flattening.")

    flattened_path = "data/lakehouse/portfolio_optimized_meta.json"
    if os.path.exists(flattened_path):
        with open(flattened_path, "r") as f:
            flat_data = json.load(f)

        md.append("| Rank | Symbol | Description | Total Weight | Market |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")

        flat_weights = flat_data.get("weights", [])
        for i, w in enumerate(flat_weights[:20]):
            md.append(f"| {i + 1} | `{w['Symbol']}` | {w.get('Description', 'N/A')} | **{w['Weight']:.2%}** | {w.get('Market', 'N/A')} |")

    md.append("\n---")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(md))

    print(f"✅ Meta-Portfolio report generated at: {output_path}")


if __name__ == "__main__":
    settings = get_settings()
    # We want to save the report in the run directory if possible
    # But for flow-meta-production, it might be in a dedicated meta run dir.
    # For now, let's use the summaries/latest root.
    out_p = Path("artifacts/summaries/latest/meta_portfolio_report.md")

    generate_meta_markdown_report("data/lakehouse/meta_optimized.json", "data/lakehouse/meta_returns.pkl", str(out_p))
