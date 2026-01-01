import json
import os
from pathlib import Path

import pandas as pd


def generate():
    run_id = os.getenv("TV_RUN_ID")
    if run_id:
        path = Path(f"artifacts/summaries/runs/{run_id}/tournament_results.json")
    else:
        path = Path("artifacts/summaries/latest/tournament_results.json")

    if not path.exists():
        # Fallback to 4D aggregate
        if run_id:
            path = Path(f"artifacts/summaries/runs/{run_id}/tournament_4d_results.json")
        else:
            path = Path("artifacts/summaries/latest/tournament_4d_results.json")

    if not path.exists():
        print(f"Results not found at {path}")
        return

    with open(path, "r") as f:
        data = json.load(f)

    rows = []
    # Results might be nested under 'results' or 'results_4d'
    if "results_4d" in data:
        # 4D case: include Mode
        for mode, res_3d in data["results_4d"].items():
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
                                "Mode": mode,
                                "Simulator": sim,
                                "Engine": eng,
                                "Profile": prof,
                                "Return (%)": f"{summary.get('annualized_return', 0) * 100:.2f}%",
                                "Sharpe": round(summary.get("avg_window_sharpe", 0), 2),
                                "Vol (%)": f"{summary.get('annualized_vol', 0) * 100:.2f}%",
                                "MDD (%)": f"{summary.get('max_drawdown', 0) * 100:.2f}%",
                                "Turnover (%)": f"{summary.get('avg_turnover', 0) * 100:.2f}%",
                            }
                        )
    else:
        res_root = data.get("results", data)
        for sim, engines in res_root.items():
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
                            "Simulator": sim,
                            "Engine": eng,
                            "Profile": prof,
                            "Return (%)": f"{summary.get('annualized_return', 0) * 100:.2f}%",
                            "Sharpe": round(summary.get("avg_window_sharpe", 0), 2),
                            "Vol (%)": f"{summary.get('annualized_vol', 0) * 100:.2f}%",
                            "MDD (%)": f"{summary.get('max_drawdown', 0) * 100:.2f}%",
                            "Turnover (%)": f"{summary.get('avg_turnover', 0) * 100:.2f}%",
                        }
                    )

    df = pd.DataFrame(rows)
    df = df.sort_values("Sharpe", ascending=False)

    output_dir = path.parent
    output_path = output_dir / "comprehensive_comparison_table.md"
    with open(output_path, "w") as f:
        f.write("# 📋 Comprehensive Tournament Comparison\n\n")
        f.write(f"**Total Combinations:** {len(df)}\n\n")
        f.write(df.to_markdown(index=False))
        f.write("\n")

    print(f"✅ Comprehensive table generated at: {output_path}")


if __name__ == "__main__":
    generate()
