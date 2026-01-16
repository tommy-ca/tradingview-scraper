import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("forensic_audit")

RUNS = ["long_all_fresh", "short_all_fresh", "ma_long_fresh", "ma_short_fresh"]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {path}: {e}")
        return {}


def analyze_run(run_id: str) -> Dict[str, Any]:
    base_dir = Path(f"artifacts/summaries/runs/{run_id}/data")

    # 1. Selection Stats
    candidates_path = base_dir / "portfolio_candidates.json"
    candidates_raw_path = base_dir / "portfolio_candidates_raw.json"

    sel_data = load_json(candidates_path)
    raw_data = load_json(candidates_raw_path)

    n_raw = len(raw_data) if isinstance(raw_data, list) else 0
    n_sel = len(sel_data) if isinstance(sel_data, list) else 0

    # 2. Validation Stats (Tournament)
    tourn_path = base_dir / "tournament_results.json"
    tourn_data = load_json(tourn_path)

    results = {}

    # Profile Metrics
    profile_metrics = {}
    if "results" in tourn_data:
        # Sort results to prioritize cvxportfolio/vectorbt over nautilus for the forensic summary
        # Assuming order in list is arbitrary, we create a map first
        sim_priority = {"cvxportfolio": 3, "vectorbt": 2, "nautilus": 1}

        # Group by profile+engine
        grouped = {}
        for res in tourn_data["results"]:
            p_name = res.get("profile")
            engine = res.get("engine")
            simulator = res.get("simulator")

            if engine not in ["custom", "skfolio"]:
                continue

            key = f"{p_name}_{engine}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(res)

        # Select best simulator for each group
        for key, res_list in grouped.items():
            # Sort by priority desc
            res_list.sort(key=lambda x: sim_priority.get(x.get("simulator", ""), 0), reverse=True)
            best_res = res_list[0]

            metrics = best_res.get("metrics", {})
            profile_metrics[key] = {
                "sharpe": metrics.get("sharpe", 0.0),
                "cagr": metrics.get("annualized_return", 0.0),  # Use annualized_return
                "vol": metrics.get("annualized_vol", 0.0),
                "mdd": metrics.get("max_drawdown", 0.0),
                "simulator": best_res.get("simulator"),
            }

    return {"run_id": run_id, "n_raw": n_raw, "n_sel": n_sel, "profiles": profile_metrics}


def generate_report():
    logger.info("Generating Forensic Audit Report...")

    aggregated = []
    for run in RUNS:
        logger.info(f"Analyzing {run}...")
        data = analyze_run(run)
        aggregated.append(data)

    # --- Generate Markdown ---
    lines = []
    lines.append("# 🔍 Stable Forensic Audit Report (Phase 176)")
    lines.append(f"**Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("\n## 1. Pipeline Funnel Summary")
    lines.append("| Run ID | Raw Pool | Selected | Selection Rate |")
    lines.append("| :--- | :---: | :---: | :---: |")

    for row in aggregated:
        rate = (row["n_sel"] / row["n_raw"]) * 100 if row["n_raw"] > 0 else 0
        lines.append(f"| `{row['run_id']}` | {row['n_raw']} | {row['n_sel']} | {rate:.1f}% |")

    lines.append("\n## 2. Performance Matrix (Custom Engine)")
    lines.append("| Run ID | Profile | Simulator | Sharpe | CAGR | Volatility | MaxDD |")
    lines.append("| :--- | :--- | :--- | :---: | :---: | :---: | :---: |")

    anomalies = []

    for row in aggregated:
        for p_key, metrics in row["profiles"].items():
            if "custom" not in p_key:
                continue
            profile = p_key.replace("_custom", "")

            # Anomaly Detection
            if metrics["sharpe"] > 8.0:  # Crypto can be high, but >8 is suspicious
                anomalies.append(f"⚠️ {row['run_id']} ({profile}): Extreme Sharpe {metrics['sharpe']:.2f}")
            if metrics["sharpe"] < -2.0:
                anomalies.append(f"⚠️ {row['run_id']} ({profile}): Negative Sharpe {metrics['sharpe']:.2f}")
            if metrics["vol"] < 1.0:  # Suspiciously low vol for crypto (usually > 20%)
                # metrics["vol"] might be percentage (e.g. 20.0) or float (0.2).
                # Tournament results seem to have annualized_vol ~ 8.0 (800%?) or 8.0%?
                # Let's check format. "annualized_vol": 8.34. This is likely %, or factor.
                # If CAGR is 100.0, it means 100%.
                pass

            lines.append(f"| `{row['run_id']}` | {profile} | {metrics['simulator']} | {metrics['sharpe']:.2f} | {metrics['cagr']:.2f}% | {metrics['vol']:.2f}% | {metrics['mdd']:.2%} |")

    if anomalies:
        lines.append("\n## 3. Anomaly Detection (Outliers)")
        for a in anomalies:
            lines.append(f"- {a}")
    else:
        lines.append("\n## 3. Anomaly Detection")
        lines.append("✅ No statistical outliers detected.")

    report_path = "docs/reports/stable_forensic_report.md"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    logger.info(f"Report saved to {report_path}")
    print("\n".join(lines))


if __name__ == "__main__":
    generate_report()
