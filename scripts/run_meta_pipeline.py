#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingview_scraper.orchestration.sdk import QuantSDK
from tradingview_scraper.telemetry.logging import setup_logging


def main():
    parser = argparse.ArgumentParser(description="Institutional Meta-Portfolio Pipeline (Thin Wrapper)")
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")
    parser.add_argument("--profiles", help="Comma-separated risk profiles to process")
    parser.add_argument("--execute-sleeves", action="store_true", help="Execute sub-sleeves in parallel using Ray")
    parser.add_argument("--run-id", help="Explicit Run ID")
    parser.add_argument("--manifest", default="configs/manifest.json", help="Manifest path")
    parser.add_argument("--sdk", action="store_true", default=True, help="Always uses SDK in this thin wrapper")

    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("run_meta_pipeline")
    logger.info(f"🚀 Starting Meta Pipeline (SDK Wrapper) for profile: {args.profile}")

    try:
        # We always use the new SDK-driven DAG orchestrator
        QuantSDK.run_pipeline("meta.full", profile=args.profile, run_id=args.run_id, profiles=args.profiles, execute_sleeves=args.execute_sleeves)
    except Exception as e:
        logger.error(f"Meta-Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
