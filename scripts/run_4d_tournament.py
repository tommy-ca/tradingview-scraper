import json
import logging
import os
from typing import Any, Dict, List

from scripts.backtest_engine import BacktestEngine
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("4d_tournament")


def run_4d_tournament():
    settings = get_settings()

    # Grand Matrix Axis
    selection_configs: List[Dict[str, Any]] = [
        {"name": "v2", "mode": "v2", "vetoes": False, "efficiency": False},
        {"name": "v3", "mode": "v3", "vetoes": False, "efficiency": False},
        {"name": "v3_spectral", "mode": "v3", "vetoes": True, "efficiency": True},
        {"name": "v3.1", "mode": "v3.1", "vetoes": False, "efficiency": False},
        {"name": "v3.1_spectral", "mode": "v3.1", "vetoes": True, "efficiency": True},
    ]
    engines = ["skfolio", "cvxportfolio", "custom"]
    profiles = ["risk_parity", "hrp", "min_variance", "max_sharpe", "benchmark", "equal_weight", "raw_pool_ew"]
    simulators = ["cvxportfolio", "nautilus", "custom"]

    # Audited Execution Parameters
    train_window = 126
    test_window = 21
    step_size = 21
    start_date = "2025-01-01"
    end_date = "2025-12-31"

    all_4d_results = {}

    # Save original state to restore later
    orig_mode = settings.features.selection_mode
    orig_vetoes = settings.features.feat_predictability_vetoes
    orig_eff = settings.features.feat_efficiency_scoring
    orig_reb = settings.features.feat_rebalance_mode

    try:
        run_dir = settings.prepare_summaries_run_dir()
        for cfg in selection_configs:
            name = str(cfg["name"])
            logger.info(f"\n🚀 GRAND TOURNAMENT: Selection = {name}")

            # Apply Config to Settings
            settings.features.selection_mode = str(cfg["mode"])
            settings.features.feat_predictability_vetoes = bool(cfg["vetoes"])
            settings.features.feat_efficiency_scoring = bool(cfg["efficiency"])
            settings.features.feat_rebalance_mode = "window"  # Enforce window mode

            # Export to ENV for sub-processes if any
            os.environ["TV_FEATURES_SELECTION_MODE"] = str(cfg["mode"])
            os.environ["TV_FEATURES_FEAT_PREDICTABILITY_VETOES"] = "1" if cfg["vetoes"] else "0"
            os.environ["TV_FEATURES_FEAT_EFFICIENCY_SCORING"] = "1" if cfg["efficiency"] else "0"
            os.environ["TV_FEATURES_FEAT_REBALANCE_MODE"] = "window"

            bt = BacktestEngine()
            res = bt.run_tournament(
                train_window=train_window,
                test_window=test_window,
                step_size=step_size,
                engines=engines,
                profiles=profiles,
                simulators=simulators,
                start_date=start_date,
                end_date=end_date,
            )

            all_4d_results[name] = res["results"]

        final_output = {
            "results_4d": all_4d_results,
            "meta": {
                "period": f"{start_date} to {end_date}",
                "dimensions": ["mode", "simulator", "engine", "profile"],
                "protocol": "Continuous Walk-Forward (100% Coverage)",
                "rebalance_mode": "window",
            },
        }
        output_path = run_dir / "grand_validation_results.json"
        # Also save as the standard name for generic tools
        tournament_json = run_dir / "tournament_4d_results.json"

        with open(output_path, "w") as f:
            json.dump(final_output, f, indent=2)
        with open(tournament_json, "w") as f:
            json.dump(final_output, f, indent=2)

        # Promote to latest
        settings.promote_summaries_latest()
        logger.info(f"✅ Grand Tournament finalized: {output_path}")

    finally:
        # Restore settings
        settings.features.selection_mode = orig_mode
        settings.features.feat_predictability_vetoes = orig_vetoes
        settings.features.feat_efficiency_scoring = orig_eff
        settings.features.feat_rebalance_mode = orig_reb


if __name__ == "__main__":
    run_4d_tournament()
