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
    parser = argparse.ArgumentParser(description="Institutional Production Pipeline (Thin Wrapper)")
    parser.add_argument("--profile", default="production", help="Workflow profile to use")
    parser.add_argument("--manifest", default="configs/manifest.json", help="Path to manifest file")
    parser.add_argument("--run-id", help="Explicit run ID to use")
    parser.add_argument("--skip-analysis", action="store_true", help="Skip heavy post-optimization analysis (Visuals)")
    parser.add_argument("--skip-validation", action="store_true", help="Skip validation backtests")
    # Legacy arguments preserved for compatibility but ignored by SDK if not in manifest
    parser.add_argument("--start-step", type=int, default=1, help="Ignored in SDK mode")
    parser.add_argument("--sdk", action="store_true", default=True, help="Always uses SDK in this thin wrapper")

    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("production_pipeline")
    logger.info(f"🚀 Starting Production Pipeline (SDK Wrapper) for profile: {args.profile}")

    try:
        # We always use the new SDK-driven DAG orchestrator
        QuantSDK.run_pipeline("alpha.full", profile=args.profile, run_id=args.run_id, skip_analysis=args.skip_analysis, skip_validation=args.skip_validation)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
