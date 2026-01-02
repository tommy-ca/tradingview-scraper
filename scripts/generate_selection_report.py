import json
from pathlib import Path

import pandas as pd


def generate_report():
    path = Path("artifacts/summaries/latest/tournament_4d_results.json")
    if not path.exists():
        print("Results not found.")
        return

    with open(path, "r") as f:
        data = json.load(f)

    results_4d = data.get("results_4d", {})

    # We want to compare v2/v3 Equal Weight (or closest proxy) vs Raw Pool Equal Weight
    # Proxy for Selected EW: 'skfolio' engine with 'equal_weight' profile (if exists), or 'custom' 'benchmark' (which is EW)
    # Baseline: 'custom' 'raw_pool_ew'

    rows = []

    # We need to aggregate across windows or use the summary
    # Let's use the summary 'total_return' and 'sharpe'

    # 1. Get Baseline (Raw Pool EW) per Simulator
    # Usually under 'custom' engine, 'raw_pool_ew' profile
    baselines = {}  # (mode, simulator) -> {ret, sharpe}

    for mode, sim_data in results_4d.items():
        for sim, engines in sim_data.items():
            # Check custom engine first
            if "custom" in engines:
                raw_data = engines["custom"].get("raw_pool_ew")
                if raw_data and raw_data.get("summary"):
                    baselines[(mode, sim)] = raw_data["summary"]

    # 2. Compare Candidates (Selected EW)
    # We'll use 'benchmark' profile as proxy for Selected EW (it EWs the selected universe)

    for mode, sim_data in results_4d.items():
        for sim, engines in sim_data.items():
            baseline = baselines.get((mode, sim))  # Note: Baseline technically changes per mode if selection changes

            if not baseline:
                # Fallback: maybe raw_pool_ew wasn't run for this mode/sim?
                continue

            # Find Selected EW (Benchmark Profile)
            # Use 'custom' engine for cleanest comparison (no optimizer noise)
            if "custom" in engines:
                sel_data = engines["custom"].get("benchmark")
                if sel_data and sel_data.get("summary"):
                    summ = sel_data["summary"]

                    sel_ret = summ.get("total_return", 0)
                    sel_sharpe = summ.get("sharpe", 0)

                    raw_ret = baseline.get("total_return", 0)
                    raw_sharpe = baseline.get("sharpe", 0)

                    rows.append(
                        {
                            "Mode": mode,
                            "Simulator": sim,
                            "Selection Alpha (Ret)": f"{sel_ret - raw_ret:.2%}",
                            "Sharpe Delta": f"{sel_sharpe - raw_sharpe:.2f}",
                            "Selected Ret": f"{sel_ret:.2%}",
                            "Raw Ret": f"{raw_ret:.2%}",
                        }
                    )

    if not rows:
        print("No comparison data found.")
        return

    df = pd.DataFrame(rows)
    df = df.sort_values(["Mode", "Simulator"])

    print(df.to_markdown(index=False))

    out_path = Path("artifacts/summaries/latest/selection_alpha_report.md")
    with open(out_path, "w") as f:
        f.write("# Selection Alpha Benchmark\n\n")
        f.write("**Metric**: Equal-Weight Selected Universe vs Equal-Weight Raw Discovery Universe.\n\n")
        f.write(df.to_markdown(index=False))

    print(f"\nReport saved to {out_path}")


if __name__ == "__main__":
    generate_report()
