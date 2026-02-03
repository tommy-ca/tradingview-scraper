from __future__ import annotations

import argparse
import logging
import os

from tradingview_scraper.backtest.engine import BacktestEngine, persist_tournament_artifacts
from tradingview_scraper.settings import get_settings

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tournament Backtest Engine")
    parser.add_argument("--mode", choices=["production", "research"], default="research")
    parser.add_argument("--train-window", type=int)
    parser.add_argument("--test-window", type=int)
    parser.add_argument("--step-size", type=int)
    parser.add_argument("--run-id", help="Explicit run ID to use")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    config = get_settings()

    # If run_id is provided, ensure settings uses it
    if args.run_id:
        os.environ["TV_RUN_ID"] = args.run_id
        # Reload settings to pick up env var
        config = get_settings()

    run_dir = config.prepare_summaries_run_dir()

    engine = BacktestEngine()
    tournament_results = engine.run_tournament(mode=args.mode, train_window=args.train_window, test_window=args.test_window, step_size=args.step_size, run_dir=run_dir)

    persist_tournament_artifacts(tournament_results, run_dir / "data")

    print("\n" + "=" * 50)
    print("TOURNAMENT COMPLETE")
    print("=" * 50)
