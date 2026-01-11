import json
from pathlib import Path

import pandas as pd


def audit_full_matrix(run_id):
    run_dir = Path(f"artifacts/summaries/runs/{run_id}")
    audit_path = run_dir / "audit.jsonl"

    if not audit_path.exists():
        print(f"Audit file not found: {audit_path}")
        return

    # Extract all success outcomes for optimization
    matrix_data = []
    with open(audit_path, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("step") == "backtest_optimize" and data.get("status") == "success":
                    ctx = data.get("context", {})
                    intent_params = data.get("intent", {}).get("params", {})

                    matrix_data.append(
                        {
                            "Window": ctx.get("window_index"),
                            "Date": ctx.get("test_start"),
                            "Engine": ctx.get("engine"),
                            "Profile": ctx.get("profile"),
                            "Regime": intent_params.get("regime"),
                            "Quadrant": intent_params.get("quadrant"),
                            "Assets": data.get("outcome", {}).get("metrics", {}).get("n_assets", 0),
                        }
                    )
            except Exception:
                continue

    df = pd.DataFrame(matrix_data)
    if df.empty:
        print("No matrix data found in audit log.")
        return

    # Performance Data
    results_path = list(run_dir.glob("**/tournament_results.json"))
    perf_df = pd.DataFrame()
    if results_path:
        with open(results_path[0], "r") as f:
            res_data = json.load(f)

        perf_rows = []
        # results[simulator][engine][profile]
        res_map = res_data.get("results", {})
        for sim, engines in res_map.items():
            if not isinstance(engines, dict):
                continue
            for eng, profiles in engines.items():
                if not isinstance(profiles, dict):
                    continue
                for prof, p_data in profiles.items():
                    if not isinstance(p_data, dict):
                        continue
                    summary = p_data.get("summary", {})
                    if summary:
                        perf_rows.append(
                            {"Simulator": sim, "Engine": eng, "Profile": prof, "Sharpe": summary.get("sharpe"), "Return": summary.get("annualized_return"), "MaxDD": summary.get("max_drawdown")}
                        )
        perf_df = pd.DataFrame(perf_rows)

    report = [
        f"# Full Matrix Risk Profile Audit Report ({run_id})",
        f"**Audit Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n## 1. Matrix Depth & Stability Audit",
        "This table shows the constituent count for each window and profile combination.",
        "Variation in count across engines for the same profile indicates fallback triggers or solver convergence issues.",
    ]

    # Depth Matrix: Window vs Profile (Mean across engines)
    depth_pivot = df.pivot_table(index="Window", columns="Profile", values="Assets", aggfunc="mean")
    report.append("\n### Mean Asset Depth per Window/Profile")
    report.append(depth_pivot.to_markdown())

    # Regime Correlation
    report.append("\n## 2. Regime & Quadrant Evolution")
    regime_timeline = df.drop_duplicates(["Window", "Regime", "Quadrant"])[["Window", "Date", "Regime", "Quadrant"]]
    report.append(regime_timeline.to_markdown(index=False))

    if not perf_df.empty:
        report.append("\n## 3. Comparative Performance Matrix (All Combos)")
        # Sort by Sharpe
        top_perf = perf_df.sort_values("Sharpe", ascending=False)
        report.append(top_perf.to_markdown(index=False))

        report.append("\n## 4. Top Performer Spotlight")
        best = top_perf.iloc[0]
        report.append(f"- **Top Strategy**: {best['Engine']} / {best['Profile']} on {best['Simulator']}")
        report.append(f"- **Sharpe**: {best['Sharpe']:.2f}")
        report.append(f"- **Return**: {best['Return']:.2%}")

    report_path = run_dir / "reports" / "full_matrix_audit_v3_2_13.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write("\n".join(report))

    print(f"Full matrix audit report generated at: {report_path}")


if __name__ == "__main__":
    audit_full_matrix("20260111-125427")
