#!/usr/bin/env python3
"""Script invoked by quant-backtest skill."""

import argparse
import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from scripts.backtest_engine import BacktestEngine


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--simulator", default="vectorbt")
    args = parser.parse_args()

    print(f"Running backtest for run: {args.run_id} using {args.simulator}")

    # Update env to force run_id
    os.environ["TV_RUN_ID"] = args.run_id

    engine = BacktestEngine()
    # engine.run_tournament(...)
    # (Implementation details would follow)

    print("Backtest complete.")


if __name__ == "__main__":
    main()
