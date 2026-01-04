import json
import logging
import os

from scripts.backtest_engine import BacktestEngine
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("grand_4d_tournament")


def run_grand_tournament():
    settings = get_settings()

    # 1. Dimensions
    selection_modes = ["v2.1", "v3.1", "v3.2"]
    rebalance_modes = ["window", "daily", "daily_5pct"]

    # Tournament Standard Scope
    engines = ["custom", "skfolio", "riskfolio", "pyportfolioopt", "cvxportfolio"]
    profiles = ["market", "benchmark", "equal_weight", "min_variance", "hrp", "max_sharpe", "barbell"]
    simulators = ["custom", "cvxportfolio", "vectorbt", "nautilus"]

    # Backtest Config (Production standards)
    train_window = 120
    test_window = 20
    step_size = 20

    # Store results in a nested structure
    # Results[reb_mode][sel_mode] -> backtest_engine result
    all_results = {}

    # Save original settings
    orig_reb = settings.features.feat_rebalance_mode
    orig_sel = settings.features.selection_mode
    orig_dynamic = settings.dynamic_universe

    # Enable dynamic universe for selection mode sweep
    settings.dynamic_universe = True

    try:
        run_dir = settings.prepare_summaries_run_dir()

        for reb_mode in rebalance_modes:
            all_results[reb_mode] = {}
            settings.features.feat_rebalance_mode = reb_mode
            os.environ["TV_FEATURES_FEAT_REBALANCE_MODE"] = reb_mode

            for sel_mode in selection_modes:
                logger.info(f"\n🏆 STARTING TOURNAMENT: Rebalance={reb_mode}, Selection={sel_mode}")

                settings.features.selection_mode = sel_mode
                os.environ["TV_FEATURES_SELECTION_MODE"] = sel_mode

                # We need a fresh BacktestEngine to reload state/data if needed
                bt = BacktestEngine()

                res = bt.run_tournament(train_window=train_window, test_window=test_window, step_size=step_size, engines=engines, profiles=profiles, simulators=simulators)

                all_results[reb_mode][sel_mode] = res["results"]

                # Incremental Save
                partial_output = {
                    "meta": {
                        "run_id": settings.run_id,
                        "dimensions": {"rebalance": rebalance_modes, "selection": selection_modes, "engines": engines, "profiles": profiles, "simulators": simulators},
                    },
                    "rebalance_audit_results": all_results,
                }
                with open(run_dir / "grand_4d_tournament_results_partial.json", "w") as f:
                    json.dump(partial_output, f, indent=2)

        # Final aggregation
        output = {
            "meta": {
                "run_id": settings.run_id,
                "dimensions": {"rebalance": rebalance_modes, "selection": selection_modes, "engines": engines, "profiles": profiles, "simulators": simulators},
            },
            "rebalance_audit_results": all_results,
        }

        out_path = run_dir / "grand_4d_tournament_results.json"
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"\n✅ Grand 4D Tournament Finalized: {out_path}")

    finally:
        # Restore settings
        settings.features.feat_rebalance_mode = orig_reb
        settings.features.selection_mode = orig_sel
        settings.dynamic_universe = orig_dynamic


if __name__ == "__main__":
    run_grand_tournament()
