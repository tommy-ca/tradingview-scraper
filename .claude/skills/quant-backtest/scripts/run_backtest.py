#!/usr/bin/env python3
"""Script invoked by quant-backtest skill."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from tradingview_scraper.backtest.engine import BacktestEngine, persist_tournament_artifacts
from tradingview_scraper.settings import get_settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", default="research")
    args = parser.parse_args()

    print(f"Starting backtest for run: {args.run_id}")

    # Initialize settings with the specific run_id
    settings = get_settings().clone(run_id=args.run_id)
    run_dir = settings.prepare_summaries_run_dir()

    # Pass explicit settings to ensure thread-safety and correctness
    engine = BacktestEngine(settings=settings)
    results = engine.run_tournament(mode=args.mode, run_dir=run_dir)
    persist_tournament_artifacts(results, run_dir / "data")

    print(f"Backtest complete. Results saved to {run_dir}/data/tournament_results.csv")


if __name__ == "__main__":
    main()
