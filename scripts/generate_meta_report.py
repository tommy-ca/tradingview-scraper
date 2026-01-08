import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, cast

import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.settings import get_settings


def generate_meta_markdown_report(meta_dir: Path, output_path: str, profiles: List[str]):
    md = []
    md.append("# 🌐 Multi-Sleeve Meta-Portfolio Report")
    md.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("\n---")

    for prof in profiles:
        prof = prof.strip()
        opt_path = meta_dir / f"meta_optimized_{prof}.json"
        rets_path = meta_dir / f"meta_returns_{prof}.pkl"
        flat_path = meta_dir / f"portfolio_optimized_meta_{prof}.json"

        if not opt_path.exists():
            continue

        with open(opt_path, "r") as f:
            meta_data = json.load(f)

        md.append(f"## 🏆 Risk Profile: {prof.upper()}")
        md.append(f"**Meta Run ID:** {meta_data.get('metadata', {}).get('run_id', 'N/A')}")

        # 1. SLEEVE ALLOCATION
        md.append("\n### 🧩 Sleeve Allocation")
        md.append("| Sleeve ID | Weight | Engine |")
        md.append("| :--- | :--- | :--- |")

        weights = sorted(meta_data.get("weights", []), key=lambda x: x["Weight"], reverse=True)
        for w in weights:
            s_id = w["Symbol"]
            weight = w["Weight"]
            md.append(f"| **{s_id}** | {weight:.2%} | Custom {prof} |")

        # 2. SLEEVE CORRELATIONS
        if rets_path.exists():
            returns_df = cast(pd.DataFrame, pd.read_pickle(rets_path))
            md.append("\n### 📊 Sleeve Correlations")
            corr = returns_df.corr()
            cols = list(corr.columns)
            md.append("| Sleeve | " + " | ".join(cols) + " |")
            md.append("| :--- | " + " | ".join([":---:"] * len(cols)) + " |")

            for idx in corr.index:
                row_vals = []
                for c in cols:
                    val = float(corr.loc[idx, c])
                    row_vals.append(f"{val:.2f}")
                md.append(f"| **{idx}** | " + " | ".join(row_vals) + " |")

        # 3. FINAL ASSET TOP 10
        if flat_path.exists():
            md.append("\n### 💎 Consolidated Top 10 Assets")
            with open(flat_path, "r") as f:
                flat_data = json.load(f)

            md.append("| Rank | Symbol | Description | Total Weight | Market |")
            md.append("| :--- | :--- | :--- | :--- | :--- |")

            flat_weights = flat_data.get("weights", [])
            for i, w in enumerate(flat_weights[:10]):
                md.append(f"| {i + 1} | `{w['Symbol']}` | {w.get('Description', 'N/A')} | **{w['Weight']:.2%}** | {w.get('Market', 'N/A')} |")

        md.append("\n---\n")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(md))

    print(f"✅ Meta-Portfolio report generated at: {output_path}")


if __name__ == "__main__":
    settings = get_settings()
    lakehouse = Path("data/lakehouse")
    out_p = Path("artifacts/summaries/latest/meta_portfolio_report.md")

    # Standard profiles to report
    target_profiles = ["barbell", "hrp", "min_variance", "equal_weight", "max_sharpe"]

    generate_meta_markdown_report(lakehouse, str(out_p), target_profiles)
