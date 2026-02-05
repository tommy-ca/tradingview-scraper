#!/usr/bin/env python3
"""
Parity Check Utility: Pickle vs Parquet.
Verifies that data migrated from Pickle to Parquet maintains exact fidelity.
"""

from __future__ import annotations

import argparse
import logging
import sys
import random
from pathlib import Path
from collections import Counter

import pandas as pd
import numpy as np

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("parity_check")


def verify_artifact(pkl_path: Path, verbose: bool = False, rtol: float = 1e-5, atol: float = 1e-8) -> str:
    """
    Compares a Pickle artifact with its Parquet counterpart.
    """
    try:
        parquet_path = pkl_path.with_suffix(".parquet")

        # Load Pickle
        try:
            pkl_obj = pd.read_pickle(pkl_path)
        except Exception as e:
            return f"LOAD_ERROR_PKL: {e}"

        # If not DataFrame/Series, skip
        if not isinstance(pkl_obj, (pd.DataFrame, pd.Series)):
            return "SKIPPED_NOT_DF"

        if not parquet_path.exists():
            return "MISSING_PARQUET"

        # Load Parquet
        try:
            pq_df = pd.read_parquet(parquet_path)
        except Exception as e:
            return f"LOAD_ERROR_PQ: {e}"

        # Transform Pickle to match Migration Logic
        # 1. Series -> DataFrame
        if isinstance(pkl_obj, pd.Series):
            pkl_df = pkl_obj.to_frame(name=pkl_path.stem)
        else:
            pkl_df = pkl_obj

        # 2. UTC Index
        if isinstance(pkl_df.index, pd.DatetimeIndex):
            if pkl_df.index.tz is None:
                pkl_df.index = pkl_df.index.tz_localize("UTC")
            else:
                pkl_df.index = pkl_df.index.tz_convert("UTC")

        # Compare
        try:
            pd.testing.assert_frame_equal(pkl_df, pq_df, rtol=rtol, atol=atol)
            return "MATCH"
        except AssertionError as e:
            if verbose:
                logger.error(f"Mismatch in {pkl_path.name}: {e}")
            return f"MISMATCH: {str(e)[:100]}..."

    except Exception as e:
        logger.error(f"Error checking {pkl_path}: {e}")
        return f"ERROR: {e}"


def main():
    parser = argparse.ArgumentParser(description="Verify Parity between Pickle and Parquet files")
    parser.add_argument("--root", type=str, default="data", help="Root directory to scan")
    parser.add_argument("--file", type=str, help="Specific pickle file to check")
    parser.add_argument("--sample", type=int, default=0, help="Check N random files from root")
    parser.add_argument("--verbose", action="store_true", help="Show detailed mismatch info")
    parser.add_argument("--rtol", type=float, default=1e-5, help="Relative tolerance for float comparison")
    parser.add_argument("--atol", type=float, default=1e-8, help="Absolute tolerance for float comparison")

    args = parser.parse_args()

    if args.file:
        pkl_path = Path(args.file)
        if not pkl_path.exists():
            logger.error(f"File not found: {pkl_path}")
            sys.exit(1)

        status = verify_artifact(pkl_path, verbose=True, rtol=args.rtol, atol=args.atol)
        logger.info(f"Result for {pkl_path.name}: {status}")
        sys.exit(0 if status == "MATCH" else 1)

    root = Path(args.root).resolve()
    if not root.exists():
        logger.error(f"Root path {root} does not exist")
        sys.exit(1)

    logger.info(f"Scanning {root} for .pkl files...")
    pickles = list(root.rglob("*.pkl"))
    logger.info(f"Found {len(pickles)} pickle artifacts.")

    if args.sample > 0 and len(pickles) > args.sample:
        logger.info(f"Sampling {args.sample} random files...")
        pickles = random.sample(pickles, args.sample)

    results = {}
    for p in pickles:
        status = verify_artifact(p, verbose=args.verbose, rtol=args.rtol, atol=args.atol)
        results[p] = status
        if status != "MATCH" and status != "SKIPPED_NOT_DF":
            logger.warning(f"{p.name}: {status}")
        elif args.verbose:
            logger.info(f"{p.name}: {status}")

    stats = Counter(results.values())
    logger.info("Parity Check Complete.")
    logger.info(f"Summary: {dict(stats)}")

    # Exit code failure if any mismatches found
    if stats["MISMATCH"] > 0 or stats.get("LOAD_ERROR_PQ", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
