import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from tradingview_scraper.settings import get_settings

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("selection_report")


def generate_selection_report(audit_path: str, output_path: str, audit_data: Optional[Dict[str, Any]] = None):
    """
    Generates a high-quality Markdown report for the universe selection process.
    """
    full_audit = {}

    if audit_data:
        full_audit = audit_data
    elif os.path.exists(audit_path):
        try:
            with open(audit_path, "r") as f:
                full_audit = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read audit file: {e}")
            return
    else:
        logger.warning(f"Audit data missing (Path: {audit_path})")
        return

    selection = full_audit.get("selection")
    if not selection:
        logger.warning("No selection data found in audit.")
        return

    md = []
    md.append("# 🧬 Natural Selection: Universe Pruning Report")
    md.append(f"**Generated on:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append(f"**Total Raw Symbols:** {selection.get('total_raw_symbols')}")
    md.append(f"**Total Selected Assets:** {selection.get('total_selected')}")
    md.append(f"**Multi-Lookbacks Used:** {selection.get('lookbacks_used')}")
    md.append("\n---")

    # 1. Summary Statistics
    md.append("## 📊 Selection Summary")
    md.append("| Metric | Value |")
    md.append("| :--- | :--- |")
    md.append(f"| Raw Discovery Pool | {selection.get('total_raw_symbols')} |")
    md.append(f"| Final Implementation Universe | {selection.get('total_selected')} |")
    md.append(f"| Pruning Factor | {((1 - selection.get('total_selected', 0) / selection.get('total_raw_symbols', 1)) * 100):.1f}% |")
    md.append("")

    # 2. Cluster Breakdown
    md.append("## 📦 Cluster-Based Natural Selection")
    md.append("Selection is performed within each risk cluster to ensure diversification while picking the best performers (Alpha Scoring).")
    md.append("| Cluster | Raw Size | Selected | Diversity (%) | Lead Selected Assets |")
    md.append("| :--- | :--- | :--- | :--- | :--- |")

    clusters = selection.get("clusters", {})
    sorted_clusters = sorted(clusters.items(), key=lambda x: int(x[0]))

    for c_id, c_data in sorted_clusters:
        size = c_data.get("size", 0)
        selected = c_data.get("selected", [])
        n_selected = len(selected)
        diversity = (n_selected / size * 100) if size > 0 else 0
        leads = ", ".join([f"`{s}`" for s in selected[:3]])
        if len(selected) > 3:
            leads += " ..."
        md.append(f"| {c_id} | {size} | {n_selected} | {diversity:.1f}% | {leads} |")

    md.append("\n---")

    # 3. Strategy Logic
    md.append("## ⚙️ Selection Strategy")
    md.append("The 'Natural Selection' process utilizes **Execution Intelligence** to prioritize assets with superior:")
    md.append("- **Momentum (30%)**: Positive trend direction and strength.")
    md.append("- **Stability (20%)**: Inverse volatility to favor smooth price action.")
    md.append("- **Convexity (20%)**: Antifragility scores from systemic tail audits.")
    md.append("- **Liquidity (30%)**: Value traded and spread proxy to ensure low slippage.")

    with open(output_path, "w") as f:
        f.write("\n".join(md))

    logger.info(f"✅ Universe Selection Report generated at: {output_path}")


if __name__ == "__main__":
    settings = get_settings()
    output_dir = settings.prepare_summaries_run_dir()

    # Try to find audit file in run dir first, then fallback to shared lakehouse
    audit_file = output_dir / "selection_audit.json"
    if not audit_file.exists():
        audit_file = Path("data/lakehouse/selection_audit.json")

    generate_selection_report(
        audit_path=str(audit_file),
        output_path=str(output_dir / "selection_audit.md"),
    )
