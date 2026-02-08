#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tradingview_scraper.orchestration.sdk import QuantSDK
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("natural_selection")


def main():
    parser = argparse.ArgumentParser(description="Natural Selection (Thin Wrapper)")
    parser.add_argument("--top-n", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--max-clusters", type=int, default=25)
    parser.add_argument("--min-momentum", type=float)
    parser.add_argument("--mode", type=str, help="Selection spec version")
    args = parser.parse_args()

    settings = get_settings()

    # Resolve parameters
    params = {}
    if args.top_n:
        params["top_n"] = args.top_n
    if args.threshold:
        params["threshold"] = args.threshold
    if args.min_momentum:
        params["min_momentum_score"] = args.min_momentum
    if args.mode:
        params["selection_mode"] = args.mode

    logger.info("🚀 Starting Natural Selection (SDK Wrapper)")

    # Execute the selection stage/pipeline
    # In v4, alpha.selection_v4 is the primary entry point
    context = QuantSDK.run_stage("alpha.selection_v4", **params)

    # Persistence (Ensuring side-effects expected by Makefile)
    run_dir = settings.summaries_runs_dir / settings.run_id
    output_path = Path(os.getenv("CANDIDATES_SELECTED", str(run_dir / "data" / "portfolio_candidates.json")))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(context, "winners"):
        logger.info(f"Writing {len(context.winners)} winners to {output_path}")
        with open(output_path, "w") as f:
            json.dump(context.winners, f, indent=2)

    logger.info("✅ Natural Selection Complete")


if __name__ == "__main__":
    main()
