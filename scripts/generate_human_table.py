import json
import os
from pathlib import Path

import pandas as pd


def generate():
    run_id = os.getenv("TV_RUN_ID")
    if run_id:
        path = Path(f"artifacts/summaries/runs/{run_id}/tournament_4d_results.json")
    else:
        path = Path("artifacts/summaries/latest/tournament_4d_results.json")

    if not path.exists():
        # Try finding the latest run directory if no TV_RUN_ID
        runs_dir = Path("artifacts/summaries/runs")
        if runs_dir.exists():
            # Get all subdirectories, excluding 'latest'
            subdirs = [d for d in runs_dir.iterdir() if d.is_dir() and d.name != "latest"]
            # Sort by modification time
            runs = sorted(subdirs, key=lambda x: x.stat().st_mtime, reverse=True)
            if runs:
                path = runs[0] / "tournament_4d_results.json"

    if not path.exists():
        print(f"Results not found at {path}")
        return

    with open(path, "r") as f:
        data = json.load(f)

    rows = []
    results_4d = data.get("results_4d", {})

    for mode, res_3d in results_4d.items():
        for sim, engines in res_3d.items():
            if not isinstance(engines, dict):
                continue
            for eng, profiles in engines.items():
                if not isinstance(profiles, dict):
                    continue
                for prof, p_data in profiles.items():
                    if prof == "_status" or p_data is None or "summary" not in p_data or p_data["summary"] is None:
                        continue

                    summary = p_data["summary"]
                    rows.append(
                        {
                            "Mode": str(mode),
                            "Simulator": str(sim),
                            "Engine": str(eng),
                            "Profile": str(prof),
                            "Return (%)": f"{summary.get('annualized_return', 0) * 100:.2f}%",
                            "Sharpe": round(float(summary.get("avg_window_sharpe", 0)), 2),
                            "Vol (%)": f"{summary.get('annualized_vol', 0) * 100:.2f}%",
                            "MDD (%)": f"{summary.get('max_drawdown', 0) * 100:.2f}%",
                            "Turnover (%)": f"{summary.get('avg_turnover', 0) * 100:.2f}%",
                        }
                    )

    if not rows:
        print("No results to display.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values("Sharpe", ascending=False)

    period = str(data.get("meta", {}).get("period", "N/A"))
    markdown_table = str(df.to_markdown(index=False))

    output_path = path.parent / "full_4d_comparison_table.md"
    with open(output_path, "w") as f:
        f.write("# 📋 Full 4D Tournament Comparison\n\n")
        f.write(f"**Period:** {period}\n")
        f.write(f"**Total Combinations:** {len(df)}\n\n")
        f.write(markdown_table)
        f.write("\n")

    print(f"✅ Full 4D table generated at: {output_path}")
    print("\n" + markdown_table)


if __name__ == "__main__":
    generate()
