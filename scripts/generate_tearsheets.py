import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import quantstats as qs

from tradingview_scraper.settings import get_settings

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("tearsheets")


def generate_tearsheets():
    settings = get_settings()
    summary_dir = settings.prepare_summaries_run_dir()
    returns_dir = summary_dir / "returns"

    if not returns_dir.exists():
        logger.warning(f"Returns directory missing: {returns_dir}")
        return

    tearsheet_root = summary_dir / "tearsheets"
    tearsheet_root.mkdir(parents=True, exist_ok=True)

    # 1. Load benchmark (SPY) for relative performance
    benchmark = None
    returns_path = Path("data/lakehouse/portfolio_returns.pkl")
    if returns_path.exists():
        try:
            all_rets = pd.read_pickle(returns_path)
            if "AMEX:SPY" in all_rets.columns:
                benchmark = all_rets["AMEX:SPY"]
                # Force naive DatetimeIndex for QuantStats compatibility
                benchmark.index = pd.to_datetime(benchmark.index)
                if benchmark.index.tz is not None:
                    benchmark.index = benchmark.index.tz_convert(None)
        except Exception as e:
            logger.warning(f"Could not load SPY benchmark: {e}")

    # 2. Iterate through pkl files in returns dir
    for pkl_path in returns_dir.glob("*.pkl"):
        try:
            name = pkl_path.stem
            logger.info(f"Generating tearsheet for: {name}")

            rets = pd.read_pickle(pkl_path)
            if rets.empty:
                continue

            # Force naive DatetimeIndex
            rets.index = pd.to_datetime(rets.index)
            if rets.index.tz is not None:
                rets.index = rets.index.tz_convert(None)

            # Output HTML
            out_html = tearsheet_root / f"{name}.html"
            qs.reports.html(rets, benchmark=benchmark, output=str(out_html), title=f"Strategy: {name}", download_filename=f"{name}.html")

        except Exception as e:
            logger.error(f"Failed to generate tearsheet for {pkl_path.name}: {e}")

    logger.info(f"Tearsheet generation complete. Root: {tearsheet_root}")


if __name__ == "__main__":
    generate_tearsheets()
