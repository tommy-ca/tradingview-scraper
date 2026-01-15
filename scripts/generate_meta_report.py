import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, cast

import numpy as np
import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.metrics import calculate_performance_metrics

logger = logging.getLogger("meta_reporting")


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

        # 0. META PERFORMANCE (Phase 159)
        if rets_path.exists():
            returns_df = cast(pd.DataFrame, pd.read_pickle(rets_path))
            if not returns_df.empty:
                md.append("\n### 📈 Meta-Performance Metrics")
                # Calculate metrics for the ensembled portfolio (Mean of sleeves weighted by opt weights)
                sleeve_weights = {w["Symbol"]: w["Weight"] for w in meta_data["weights"]}

                # Align columns and weights
                cols = [c for c in returns_df.columns if c in sleeve_weights]
                w_vec = np.array([sleeve_weights[c] for c in cols])

                # Compute ensembled portfolio returns
                port_rets = (returns_df[cols] * w_vec).sum(axis=1)

                metrics = calculate_performance_metrics(port_rets)

                md.append("| Metric | Value |")
                md.append("| :--- | :--- |")
                md.append(f"| **Sharpe Ratio** | {metrics.get('sharpe', 0):.4f} |")
                md.append(f"| **Ann. Return** | {metrics.get('annualized_return', 0):.2%} |")
                md.append(f"| **Ann. Volatility** | {metrics.get('annualized_vol', 0):.2%} |")
                md.append(f"| **Max Drawdown** | {metrics.get('max_drawdown', 0):.2%} |")

                # Success Rate (Custom metric for rebalance stability)
                win_rate = (port_rets > 0).mean()
                md.append(f"| **Win Rate** | {win_rate:.1%} |")

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

        # 4. SLEEVE DATA HEALTH (CR-828)
        manifest_path = meta_dir / f"meta_manifest_{prof}.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)

                md.append("\n### 🏥 Sleeve Data Health Summary")
                md.append("| Sleeve | Run ID | Health Status |")
                md.append("| :--- | :--- | :--- |")

                for sleeve in manifest.get("sleeves", []):
                    s_id = sleeve["id"]
                    run_path = Path(sleeve["run_path"])
                    health_file = run_path / "reports" / "selection" / "data_health_selected.md"
                    if not health_file.exists():
                        health_file = run_path / "reports" / "selection" / "data_health_raw.md"

                    status = "UNKNOWN"
                    if health_file.exists():
                        with open(health_file, "r") as hf:
                            content = hf.read()
                        if "OK" in content and "MISSING" not in content and "STALE" not in content:
                            status = "✅ HEALTHY"
                        elif "STALE" in content or "DEGRADED" in content:
                            status = "⚠️ DEGRADED"
                        elif "MISSING" in content:
                            status = "❌ MISSING DATA"

                    md.append(f"| {s_id} | {run_path.name} | {status} |")
            except Exception as e:
                logger.error(f"Failed to include sleeve health: {e}")

        md.append("\n---\n")

    out_dir = Path(output_path).parent
    # CR-831: Workspace Isolation - Ensure output dir exists
    # If this is artifacts/summaries/latest, it's usually a symlink
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        pass
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
