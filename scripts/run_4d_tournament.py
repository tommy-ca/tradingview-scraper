import json
import logging
import os

from scripts.backtest_engine import BacktestEngine
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("4d_tournament")


def run_4d_tournament():
    settings = get_settings()

    selection_modes = ["v2", "v3", "v3.1"]
    engines = ["skfolio", "cvxportfolio", "custom"]
    profiles = ["hrp", "risk_parity", "min_variance", "max_sharpe", "benchmark", "market", "raw_pool_ew"]
    simulators = ["cvxportfolio", "nautilus", "custom"]

    train_window = 126
    test_window = 20
    step_size = 126
    start_date = "2025-01-01"
    end_date = "2025-12-31"

    all_4d_results = {}
    original_mode = settings.features.selection_mode

    try:
        run_dir = settings.prepare_summaries_run_dir()
        for mode in selection_modes:
            logger.info(f"\n🚀 VERIFICATION TOURNAMENT: Selection Mode = {mode}")
            os.environ["TV_FEATURES_SELECTION_MODE"] = mode
            settings.features.selection_mode = mode
            settings.features.feat_rebalance_mode = "window"  # Enforce window mode

            bt = BacktestEngine()
            res = bt.run_tournament(
                train_window=train_window, test_window=test_window, step_size=step_size, engines=engines, profiles=profiles, simulators=simulators, start_date=start_date, end_date=end_date
            )

            all_4d_results[mode] = res["results"]

        final_output = {"results_4d": all_4d_results, "meta": {"period": f"{start_date} to {end_date}", "dimensions": ["mode", "simulator", "engine", "profile"]}}
        output_path = run_dir / "tournament_4d_results.json"
        with open(output_path, "w") as f:
            json.dump(final_output, f, indent=2)

        # Promote to latest
        settings.promote_summaries_latest()
        logger.info(f"✅ Tournament results finalized and promoted to 'latest': {output_path}")

    finally:
        os.environ["TV_FEATURES_SELECTION_MODE"] = original_mode


if __name__ == "__main__":
    run_4d_tournament()
