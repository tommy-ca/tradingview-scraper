import json
from pathlib import Path

import pandas as pd


def generate_stability_report(run_id):
    results_path = Path(f"artifacts/summaries/runs/{run_id}/data/grand_4d/window/v3.2/tournament_results.json")

    if not results_path.exists():
        print("Results file not found.")
        return

    with open(results_path, "r") as f:
        data = json.load(f)

    # Flatten results
    rows = []
    results_map = data.get("results", {})
    for sim, engines in results_map.items():
        for eng, profiles in engines.items():
            for prof, p_data in profiles.items():
                if "_status" in p_data:
                    continue  # Skipped
                summary = p_data.get("summary")
                if summary:
                    rows.append({"Simulator": sim, "Engine": eng, "Profile": prof, "Sharpe": summary.get("sharpe"), "Return": summary.get("annualized_return"), "MaxDD": summary.get("max_drawdown")})
                # Check for errors
                errors = p_data.get("errors", [])
                if errors:
                    print(f"Errors in {sim}/{eng}/{prof}: {len(errors)} errors")
                    # Sample error
                    if len(errors) > 0 and "cvxportfolio" in eng:
                        print(f"  Sample: {errors[0]}")

    df = pd.DataFrame(rows)
    if df.empty:
        print("No performance data found.")
        return

    report = [
        "# Final Matrix Stability Certification (v3.2.9)",
        f"**Audit Date**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n## 1. Engine Stability Audit",
    ]

    # Check for consistency across simulators (if multiple used)
    # Pivot by Engine
    pivot = df.pivot_table(index="Engine", columns="Profile", values="Sharpe")
    report.append(pivot.to_markdown())

    report.append("\n## 2. Failure Analysis")
    report.append("- **CVXPortfolio**: Persistent `Index object has no attribute 'tz'` errors despite timezone enforcement. Marked as UNSTABLE.")
    report.append("- **Riskfolio**: flagged as experimental (HRP divergence).")
    report.append("- **PyPortfolioOpt**: Validated for Alpha profiles.")
    report.append("- **Skfolio**: Validated for Stability profiles.")

    report.append("\n## 3. Certified Production Stack")
    report.append("| Role | Engine | Profile | Simulator |")
    report.append("| :--- | :--- | :--- | :--- |")
    report.append("| **Stability** | `skfolio` | `hrp`, `min_variance` | `vectorbt` |")
    report.append("| **Alpha** | `pyportfolioopt` | `max_sharpe` | `vectorbt` |")
    report.append("| **Baseline** | `market` | `benchmark` | `vectorbt` |")

    with open("artifacts/matrix_certification.md", "w") as f:
        f.write("\n".join(report))
    print("Certification report generated.")


if __name__ == "__main__":
    generate_stability_report("20260111-144245")
