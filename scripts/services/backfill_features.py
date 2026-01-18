import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np
import json
from tqdm import tqdm

sys.path.append(os.getcwd())
from tradingview_scraper.utils.technicals import TechnicalRatings
from tradingview_scraper.utils.audit import get_df_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("backfill_features")


def backfill_features(candidates_path: str, returns_matrix_path: str, output_path: str, step_size: int = 10):
    """
    Generates a historical features_matrix.parquet by reconstructing technical ratings
    from raw OHLCV data for all assets in the universe.
    """
    # 1. Load Universe
    if not os.path.exists(candidates_path):
        logger.error(f"Candidates file not found: {candidates_path}")
        return

    with open(candidates_path, "r") as f:
        candidates = json.load(f)

    # Extract unique physical symbols
    symbols = list(set([c.get("physical_symbol") or c.get("symbol") for c in candidates]))
    logger.info(f"Loaded {len(symbols)} unique physical symbols for backfill.")

    # 2. Get Date Range from Returns Matrix
    if not os.path.exists(returns_matrix_path):
        logger.error(f"Returns matrix not found: {returns_matrix_path}")
        return

    returns_df = pd.read_parquet(returns_matrix_path)
    # Optimization: Only calculate for rebalance windows to save time
    all_dates = returns_df.index
    dates = all_dates[::step_size]
    logger.info(f"Targeting {len(dates)} rebalance dates (step={step_size}) from {dates[0]} to {dates[-1]}")

    # 3. Process Symbols
    all_features = {}
    lakehouse = Path("data/lakehouse")

    for symbol in tqdm(symbols, desc="Backfilling Symbols"):
        safe_sym = symbol.replace(":", "_")
        ohlcv_path = lakehouse / f"{safe_sym}_1d.parquet"

        if not ohlcv_path.exists():
            logger.warning(f"  [{symbol}] OHLCV data missing at {ohlcv_path}")
            continue

        try:
            df = pd.read_parquet(ohlcv_path)
            df.columns = [c.lower() for c in df.columns]

            # Robust Index Alignment (UTC Naive)
            df.index = pd.to_datetime(df.index)
            if hasattr(df.index, "tz") and df.index.tz is not None:
                df.index = df.index.tz_convert(None)

            # Result Series
            ma_series = pd.Series(index=dates, dtype=float)
            osc_series = pd.Series(index=dates, dtype=float)
            all_series = pd.Series(index=dates, dtype=float)

            # TechnicalRatings requires enough history for 200 SMA and Ichimoku (26 lag)
            min_history = 250

            for date in dates:
                # Align search date (ensure naive comparison)
                target_date = pd.to_datetime(date)
                if hasattr(target_date, "tz") and target_date.tz is not None:
                    target_date = target_date.tz_convert(None)

                # Slice history up to this date
                history = df[df.index <= target_date]
                if len(history) < min_history:
                    continue

                # Reconstruct
                # Pass explicit DataFrame slice to ensure it's not a Series
                history_df = pd.DataFrame(history)
                ma_val = TechnicalRatings.calculate_recommend_ma(history_df)
                osc_val = TechnicalRatings.calculate_recommend_other(history_df)
                all_val = TechnicalRatings.calculate_recommend_all(history_df, ma_val, osc_val)

                ma_series.loc[date] = ma_val
                osc_series.loc[date] = osc_val
                all_series.loc[date] = all_val

            all_features[(symbol, "recommend_ma")] = ma_series
            all_features[(symbol, "recommend_other")] = osc_series
            all_features[(symbol, "recommend_all")] = all_series

        except Exception as e:
            logger.error(f"  [{symbol}] Failed: {e}")

    if not all_features:
        logger.error("No features generated.")
        return

    # 4. Construct Multi-Index DataFrame
    logger.info("Consolidating features matrix...")
    final_df = pd.DataFrame(all_features)
    final_df.columns.names = ["symbol", "feature"]

    # 5. Save
    output_path_p = Path(output_path)
    output_path_p.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_parquet(output_path)

    logger.info(f"✅ Features matrix saved to {output_path}")
    logger.info(f"Shape: {final_df.shape} | Hash: {get_df_hash(final_df)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="Path to portfolio_candidates.json")
    parser.add_argument("--returns", required=True, help="Path to returns_matrix.parquet")
    parser.add_argument("--output", required=True, help="Output path for features_matrix.parquet")
    parser.add_argument("--step", type=int, default=10, help="Step size for backfill (rebalance frequency)")
    args = parser.parse_args()

    backfill_features(args.candidates, args.returns, args.output, args.step)
