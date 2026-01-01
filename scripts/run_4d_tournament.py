import json
import logging
import os

from scripts.backtest_engine import BacktestEngine
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("4d_tournament")


def run_4d_tournament():
    """
    Executes a 4D Tournament Matrix:
    D1: Selection Mode (v2, v3)
    D2: Engines (skfolio, riskfolio, pyportfolioopt, cvxportfolio, custom)
    D3: Profiles (hrp, risk_parity, barbell, benchmark, market)
    D4: Simulators (cvxportfolio, nautilus)
    """
    settings = get_settings()

    selection_modes = ["v2", "v3"]
    engines = ["skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio", "custom"]
    profiles = ["hrp", "risk_parity", "barbell", "benchmark", "market"]
    simulators = ["cvxportfolio", "vectorbt", "custom", "nautilus"]

    # Tournament parameters - optimized for high-fidelity coverage
    train_window = 126  # Half year training
    test_window = 20
    step_size = 63  # Quarterly rebalance steps
    start_date = "2025-01-01"
    end_date = "2025-12-31"

    all_4d_results = {}

    # We need to preserve the original selection mode
    original_mode = settings.features.selection_mode

    try:
        for mode in selection_modes:
            logger.info(f"\n🚀 STARTING TOURNAMENT PHASE: Selection Mode = {mode}")

            # Update settings for this run
            os.environ["TV_FEATURES_SELECTION_MODE"] = mode
            settings.features.selection_mode = mode

            bt = BacktestEngine()
            res = bt.run_tournament(
                train_window=train_window, test_window=test_window, step_size=step_size, engines=engines, profiles=profiles, simulators=simulators, start_date=start_date, end_date=end_date
            )

            # Save as standard tournament_results.json for report generation
            run_dir = settings.prepare_summaries_run_dir()
            results_path = run_dir / "tournament_results.json"
            with open(results_path, "w") as f:
                json.dump({"meta": res["meta"], "results": res["results"]}, f, indent=2)

            # Save returns
            if "returns" in res:
                ret_dir = run_dir / "returns"
                ret_dir.mkdir(exist_ok=True)
                for k, v in res["returns"].items():
                    v.to_pickle(ret_dir / f"{k}.pkl")

            # Run standard report generator for this mode
            logger.info(f"📊 Generating reports for mode: {mode}")
            import subprocess

            subprocess.run(["uv", "run", "scripts/generate_reports.py"], env=os.environ, check=True)

            # Move reports to a mode-specific folder to avoid overwriting
            mode_report_dir = run_dir / f"reports_{mode}"
            mode_report_dir.mkdir(exist_ok=True)
            # Find all MD and PNG files in run_dir and move them
            for item in run_dir.iterdir():
                if item.suffix in [".md", ".png"] and item.is_file():
                    target = mode_report_dir / item.name
                    if target.exists():
                        target.unlink()
                    os.rename(item, target)

            all_4d_results[mode] = res["results"]

            # Save intermediate results for safety
            with open(run_dir / f"results_3d_{mode}.json", "w") as f:
                json.dump(res["results"], f, indent=2)

        # Final Aggregation
        final_output = {
            "meta": {
                "dimensions": ["selection_mode", "simulator", "engine", "profile"],
                "selection_modes": selection_modes,
                "engines": engines,
                "profiles": profiles,
                "simulators": simulators,
                "period": f"{start_date} to {end_date}",
                "train_window": train_window,
                "test_window": test_window,
            },
            "results_4d": all_4d_results,
        }

        run_dir = settings.prepare_summaries_run_dir()
        output_path = run_dir / "tournament_4d_results.json"
        with open(output_path, "w") as f:
            json.dump(final_output, f, indent=2)

        logger.info(f"\n✅ 4D Tournament Complete. Results saved to: {output_path}")

    finally:
        # Restore original mode
        os.environ["TV_FEATURES_SELECTION_MODE"] = original_mode
        settings.features.selection_mode = original_mode


if __name__ == "__main__":
    run_4d_tournament()
