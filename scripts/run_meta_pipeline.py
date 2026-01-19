import argparse
import json
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
from scripts.parallel_orchestrator_ray import execute_parallel_sleeves
from tradingview_scraper.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("run_meta_pipeline")


def run_meta_pipeline(meta_profile: str, profiles: Optional[List[str]] = None, execute_sleeves: bool = False):
    """
    Streamlined Meta-Portfolio Pipeline (Alpha Flow).
    Executes Build -> Optimize -> Flatten -> Report in one go.
    Supports fractal recursion via build_meta_returns.
    """
    settings = get_settings()
    target_profiles = profiles or settings.profiles.split(",")
    lakehouse = Path("data/lakehouse")

    logger.info(f"🚀 Starting Meta-Portfolio Pipeline: {meta_profile}")

    # CR-850: Parallel Sleeve Execution (Phase 223)
    if execute_sleeves:
        logger.info(">>> STAGE 0: Parallel Sleeve Production (Ray)")

        # Load manifest to find sleeves that need execution
        with open("configs/manifest.json", "r") as f:
            manifest_data = json.load(f)

        meta_cfg = manifest_data.get("profiles", {}).get(meta_profile)
        if meta_cfg:
            sleeves_to_run = []
            for s in meta_cfg.get("sleeves", []):
                # If run_id is a placeholder or missing, we execute it
                if "baseline" in str(s.get("run_id", "")) or not s.get("run_id"):
                    import datetime

                    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    new_run_id = f"ray_{s['profile']}_{ts}"
                    s["run_id"] = new_run_id
                    sleeves_to_run.append({"profile": s["profile"], "run_id": new_run_id})

            if sleeves_to_run:
                results = execute_parallel_sleeves(sleeves_to_run)
                for res in results:
                    if res["status"] == "success":
                        logger.info(f"✅ Sleeve {res['profile']} complete ({res['duration']:.1f}s)")
                    else:
                        logger.error(f"❌ Sleeve {res['profile']} FAILED: {res.get('error', 'Unknown Error')}")

                # Update transient manifest context or persist if needed
                logger.info("Parallel execution phase complete.")

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
    parser.add_argument("--execute-sleeves", action="store_true", help="Execute sub-sleeves in parallel using Ray")
    args = parser.parse_args()

    target_profs = args.profiles.split(",") if args.profiles else None
    run_meta_pipeline(args.profile, target_profs, execute_sleeves=args.execute_sleeves)
