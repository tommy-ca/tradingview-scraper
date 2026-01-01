import json
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("4d_reporting")


def fmt_pct(val):
    if val is None:
        return "N/A"
    return f"{float(val):.2%}"


def run_4d_reporting():
    path = Path("artifacts/summaries/latest/tournament_4d_results.json")
    if not path.exists():
        logger.error("4D Tournament results not found.")
        return

    with open(path, "r") as f:
        data = json.load(f)

    results_4d = data["results_4d"]
    rows = []

    # Flatten 4D structure for analysis
    for mode, res_3d in results_4d.items():
        for sim, engines in res_3d.items():
            for eng, profiles in engines.items():
                if eng == "_status":
                    continue
                for prof, p_data in profiles.items():
                    if prof == "_status" or p_data is None or "summary" not in p_data or p_data["summary"] is None:
                        continue

                    summary = p_data["summary"]
                    rows.append(
                        {
                            "Mode": mode,
                            "Simulator": sim,
                            "Engine": eng,
                            "Profile": prof,
                            "Ann. Return": summary.get("annualized_return", 0),
                            "Sharpe": summary.get("avg_window_sharpe", 0),
                            "Vol": summary.get("annualized_vol", 0),
                            "MDD": summary.get("max_drawdown", 0),
                            "Turnover": summary.get("avg_turnover", 0),
                        }
                    )

    df = pd.DataFrame(rows)

    # 1. Unified Comparison Report
    md = []
    md.append("# 🌐 4D Tournament Unified Comparison Report")
    md.append(f"**Period:** {data['meta']['period']}")
    md.append("**Dimensions:** Selection Mode, Simulator, Engine, Profile")
    md.append("\n---")

    md.append("## 🏆 Top 10 Best Performers (by Sharpe)")
    top_10 = df.sort_values("Sharpe", ascending=False).head(10).copy()
    for col in ["Ann. Return", "Vol", "MDD", "Turnover"]:
        top_10[col] = top_10[col].apply(fmt_pct)
    md.append(top_10.to_markdown(index=False))

    md.append("\n## 🚨 Outlier Spotting: Bottom 10 Performers (by Sharpe)")
    bottom_10 = df.sort_values("Sharpe", ascending=True).head(10).copy()
    for col in ["Ann. Return", "Vol", "MDD", "Turnover"]:
        bottom_10[col] = bottom_10[col].apply(fmt_pct)
    md.append(bottom_10.to_markdown(index=False))

    # 2. Fidelity Check (Simulator Divergence)
    md.append("\n## 🔍 Fidelity Check: Simulator Divergence")
    md.append("Measures the performance gap between `cvxportfolio` (friction) and `nautilus` (baseline).")

    fidelity = df.pivot_table(index=["Mode", "Engine", "Profile"], columns="Simulator", values="Sharpe")
    if "cvxportfolio" in fidelity.columns and "nautilus" in fidelity.columns:
        fidelity["Gap"] = fidelity["nautilus"] - fidelity["cvxportfolio"]
        fidelity_md = fidelity.sort_values("Gap", ascending=False).head(10)
        md.append("\n### Largest Divergences (Optimistic Baseline vs. Friction)")
        md.append(fidelity_md.to_markdown())
    else:
        md.append("\nInsufficient simulator data for cross-check.")

    # 3. Selection Spec Delta (V2 vs V3)
    md.append("\n## 🧬 Selection Spec Delta: V2 vs V3 Performance")
    selection_pivot = df.pivot_table(index=["Simulator", "Engine", "Profile"], columns="Mode", values="Sharpe")
    if "v2" in selection_pivot.columns and "v3" in selection_pivot.columns:
        selection_pivot["Improvement (V2 vs V3)"] = selection_pivot["v2"] - selection_pivot["v3"]
        sel_md = selection_pivot.sort_values("Improvement (V2 vs V3)", ascending=False)
        md.append(sel_md.to_markdown())

    # 4. Winners per Profile
    md.append("\n## 🥇 Winners per Profile")
    md.append("Identifies the best Selection Mode and Portfolio Engine for each risk profile.")

    profile_winners = []
    for prof in df["Profile"].unique():
        prof_df = df[df["Profile"] == prof]
        if prof_df.empty:
            continue
        winner = prof_df.sort_values("Sharpe", ascending=False).iloc[0]
        profile_winners.append(
            {
                "Profile": prof.upper(),
                "Best Mode": winner["Mode"],
                "Best Engine": winner["Engine"],
                "Best Simulator": winner["Simulator"],
                "Max Sharpe": f"{winner['Sharpe']:.2f}",
                "Ann. Return": fmt_pct(winner["Ann. Return"]),
            }
        )

    if profile_winners:
        md.append(pd.DataFrame(profile_winners).to_markdown(index=False))

    # 5. Engine Stability Benchmark
    md.append("\n## 🛠️ Engine Stability Benchmark")
    eng_stats = df.groupby("Engine").agg({"Sharpe": ["mean", "std", "count"], "Ann. Return": "mean"})
    eng_stats.columns = ["Avg Sharpe", "Sharpe Std", "Samples", "Avg Return"]
    md.append(eng_stats.sort_values("Avg Sharpe", ascending=False).to_markdown())

    # Write unified report
    output_path = Path("artifacts/summaries/latest/tournament_4d_unified_report.md")
    with open(output_path, "w") as f:
        f.write("\n".join(md))

    logger.info(f"✅ Unified 4D report generated at: {output_path}")


if __name__ == "__main__":
    run_4d_reporting()
