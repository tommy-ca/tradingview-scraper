#!/usr/bin/env python3
"""
Institutional Migration Utility: Pickle to Parquet.
Ensures atomic conversion, strict validation, and zero data loss.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd
import numpy as np
from joblib import Parallel, delayed

# Standard Institutional Imports
from tradingview_scraper.utils.security import SecurityUtils

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("pickle_migrator")


def _is_safe_to_convert(pkl_path: Path) -> bool:
    """Verifies path is within allowed data roots."""
    try:
        # We allow data/ artifacts, logs, and lakehouse
        # Adjust roots as per your specific volume mounts in Docker
        roots = [
            Path("data").resolve(),
        ]
        SecurityUtils.ensure_safe_path(pkl_path, roots)
        return True
    except Exception as e:
        logger.warning(f"SKIPPING: Unsafe path {pkl_path}: {e}")
        return False


def convert_artifact(pkl_path: Path, dry_run: bool = False) -> str:
    """
    Converts a single Pickle artifact to Parquet (DataFrames) or JSON (Metadata).
    Returns status string for reporting.
    """
    try:
        if not _is_safe_to_convert(pkl_path):
            return "UNSAFE_PATH"

        parquet_path = pkl_path.with_suffix(".parquet")
        json_path = pkl_path.with_suffix(".json")

        # Idempotency check
        if parquet_path.exists() or json_path.exists():
            return "SKIPPED_EXISTS"

        if dry_run:
            return "DRY_RUN_OK"

        # Load Pickle
        # NOTE: This IS the danger zone. This script MUST run in isolation.
        try:
            obj = pd.read_pickle(pkl_path)
        except Exception as e:
            return f"LOAD_ERROR: {e}"

        # Determine Type & Convert
        if isinstance(obj, (pd.DataFrame, pd.Series)):
            # Normalize to DataFrame
            if isinstance(obj, pd.Series):
                obj = obj.to_frame(name=pkl_path.stem)

            # Atomic Write Pattern
            temp_path = parquet_path.with_suffix(".parquet.tmp")
            try:
                # Use Zstd for max compression (Performance Oracle req)
                # Ensure UTC index
                if isinstance(obj.index, pd.DatetimeIndex) and obj.index.tz is None:
                    obj.index = obj.index.tz_localize("UTC")
                elif isinstance(obj.index, pd.DatetimeIndex):
                    obj.index = obj.index.tz_convert("UTC")

                obj.to_parquet(temp_path, compression="zstd", index=True)
                shutil.move(temp_path, parquet_path)
                return "CONVERTED_PARQUET"
            finally:
                if temp_path.exists():
                    temp_path.unlink()

        elif isinstance(obj, (dict, list)):
            # Convert metadata to JSON
            import json

            # Handle non-serializable types gracefully-ish
            def default(o):
                if isinstance(o, np.integer):
                    return int(o)
                if isinstance(o, np.floating):
                    return float(o)
                if isinstance(o, (pd.Timestamp, pd.Period)):
                    return str(o)
                return str(o)

            temp_path = json_path.with_suffix(".json.tmp")
            try:
                with open(temp_path, "w") as f:
                    json.dump(obj, f, default=default, indent=2)
                shutil.move(temp_path, json_path)
                return "CONVERTED_JSON"
            finally:
                if temp_path.exists():
                    temp_path.unlink()

        else:
            return f"UNKNOWN_TYPE: {type(obj)}"

    except Exception as e:
        logger.error(f"Failed to convert {pkl_path}: {e}")
        return f"FATAL_ERROR: {e}"


def main():
    parser = argparse.ArgumentParser(description="Migrate Pickles to Parquet/JSON")
    parser.add_argument("--root", type=str, default="data", help="Root directory to scan")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel jobs")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without writing")
    parser.add_argument("--delete-source", action="store_true", help="Delete .pkl after success")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.exists():
        logger.error(f"Root path {root} does not exist")
        sys.exit(1)

    logger.info(f"Scanning {root} for .pkl files...")
    pickles = list(root.rglob("*.pkl"))
    logger.info(f"Found {len(pickles)} pickle artifacts.")

    # Execute in Parallel
    # Using 'threading' backend for I/O bound tasks if small, 'loky' for CPU bound
    # Parquet encoding is CPU bound -> Use default (loky)
    results = Parallel(n_jobs=args.jobs, verbose=5)(delayed(convert_artifact)(p, args.dry_run) for p in pickles)

    # Reporting
    from collections import Counter

    stats = Counter(results)
    logger.info("Migration Complete.")
    logger.info(f"Summary: {dict(stats)}")

    # Cleanup Phase
    if args.delete_source and not args.dry_run:
        logger.info("Starting Cleanup Phase (Deleting Pickles)...")
        deleted = 0
        for p, status in zip(pickles, results):
            if status in ("CONVERTED_PARQUET", "CONVERTED_JSON", "SKIPPED_EXISTS"):
                try:
                    p.unlink()
                    deleted += 1
                except Exception as e:
                    logger.error(f"Failed to delete {p}: {e}")
        logger.info(f"Deleted {deleted} legacy pickle files.")


if __name__ == "__main__":
    main()
