#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingview_scraper.orchestration.sdk import QuantSDK
from tradingview_scraper.settings import get_settings


def main():
    parser = argparse.ArgumentParser(description="Clustered Optimization (Thin Wrapper)")
    parser.add_argument("--profile", help="Optimization profile name")
    parser.add_argument("--returns", help="Path to returns matrix")
    parser.add_argument("--clusters", help="Path to clusters file")

    args = parser.parse_args()

    settings = get_settings()
    logger = logging.getLogger("optimize_clustered_v2")
    logger.info("🚀 Starting Clustered Optimization (SDK Wrapper)")

    params = {}
    if args.profile:
        params["profile"] = args.profile
    if args.returns:
        params["returns_path"] = args.returns
    if args.clusters:
        params["clusters_path"] = args.clusters

    try:
        # Call the new risk optimization stage
        QuantSDK.run_stage("risk.optimize", **params)
    except Exception as e:
        logger.error(f"Optimization failed: {e}")
        sys.exit(1)

    logger.info("✅ Optimization Complete")


if __name__ == "__main__":
    main()
