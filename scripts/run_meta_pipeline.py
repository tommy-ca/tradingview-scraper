import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

sys.path.append(os.getcwd())
from scripts.build_meta_returns import build_meta_returns
from scripts.flatten_meta_weights import flatten_weights
from scripts.generate_meta_report import generate_meta_markdown_report
from scripts.optimize_meta_portfolio import optimize_meta
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("run_meta_pipeline")


def run_meta_pipeline(meta_profile: str, profiles: Optional[List[str]] = None):
    """
    Streamlined Meta-Portfolio Pipeline (Alpha Flow).
    Executes Build -> Optimize -> Flatten -> Report in one go.
    Supports fractal recursion via build_meta_returns.
    """
    settings = get_settings()
    target_profiles = profiles or settings.profiles.split(",")
    lakehouse = Path("data/lakehouse")

    logger.info(f"🚀 Starting Meta-Portfolio Pipeline: {meta_profile}")

    # 1. Build Returns (Recursive)
    logger.info(">>> STAGE 1: Aggregating Sleeve Returns")
    build_meta_returns(meta_profile, str(lakehouse / "meta_returns.pkl"), target_profiles)

    # 2. Optimize
    logger.info(">>> STAGE 2: Meta-Optimization")
    optimize_meta(str(lakehouse), str(lakehouse / "meta_optimized.json"), meta_profile=meta_profile)

    # 3. Flatten
    logger.info(">>> STAGE 3: Recursive Weight Flattening")
    for prof in target_profiles:
        prof = prof.strip()
        flatten_weights(meta_profile, str(lakehouse / "portfolio_optimized_meta.json"), profile=prof)

    # 4. Reporting
    logger.info(">>> STAGE 4: Generating Forensic Report")
    generate_meta_markdown_report(lakehouse, "artifacts/summaries/latest/meta_portfolio_report.md", target_profiles, meta_profile)

    logger.info(f"✅ Meta-Portfolio Pipeline COMPLETE: {meta_profile}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")
    parser.add_argument("--profiles", help="Comma-separated risk profiles to process")
    args = parser.parse_args()

    target_profs = args.profiles.split(",") if args.profiles else None
    run_meta_pipeline(args.profile, target_profs)
