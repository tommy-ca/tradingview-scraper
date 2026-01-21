import argparse
import json
import logging
import os
import sys
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


def run_meta_pipeline(meta_profile: str, profiles: Optional[List[str]] = None, execute_sleeves: bool = False, use_native_ray: bool = False, run_id: Optional[str] = None):
    """
    Streamlined Meta-Portfolio Pipeline (Alpha Flow).
    Executes Build -> Optimize -> Flatten -> Report in one go.
    Supports fractal recursion via build_meta_returns.
    """
    settings = get_settings()
    target_profiles = profiles or settings.profiles.split(",")

    # CR-851: Meta-Run Isolation (Phase 242)
    import datetime

    if not run_id:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        run_id = f"{meta_profile}_{ts}"

    # Establish Isolated Workspace
    run_dir = (settings.summaries_runs_dir / run_id).resolve()

    # CR-FIX: Ensure global context for internal modules (AuditLedger, Settings)
    os.environ["TV_RUN_ID"] = run_id
    # Force reload settings to pick up new run_id
    get_settings.cache_clear()

    run_data_dir = run_dir / "data"
    run_data_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"🚀 Starting Meta-Portfolio Pipeline: {meta_profile}")
    logger.info(f"📂 Workspace: {run_dir}")
    logger.info(f"📂 Data Dir: {run_data_dir}")

    # CR-850: Parallel Sleeve Execution (Phase 223)
    if execute_sleeves:
        logger.info(f">>> STAGE 0: Parallel Sleeve Production (Ray {'Native' if use_native_ray else 'Subprocess'})")

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
                if use_native_ray:
                    from scripts.parallel_orchestrator_native import execute_parallel_sleeves_native

                    results = execute_parallel_sleeves_native(sleeves_to_run)
                else:
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
    # Output to isolated run directory
    build_meta_returns(meta_profile, str(run_data_dir / "meta_returns.pkl"), target_profiles, base_dir=run_data_dir)

    # 2. Optimize
    logger.info(">>> STAGE 2: Meta-Optimization")
    # optimize_meta infers base_dir from input path (run_data_dir / "meta_returns.pkl")
    optimize_meta(str(run_data_dir / "meta_returns.pkl"), str(run_data_dir / "meta_optimized.json"), meta_profile=meta_profile)

    # 3. Flatten
    logger.info(">>> STAGE 3: Recursive Weight Flattening")
    for prof in target_profiles:
        prof = prof.strip()
        # flatten_weights needs to know where to look. We pass the output path in run_data_dir.
        flatten_weights(meta_profile, str(run_data_dir / "portfolio_optimized_meta.json"), profile=prof)

    # 4. Reporting
    logger.info(">>> STAGE 4: Generating Forensic Report")
    # Generate report inside the run directory AND latest summary
    report_path = run_dir / "reports" / "meta_portfolio_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    generate_meta_markdown_report(run_data_dir, str(report_path), target_profiles, meta_profile)

    # Also update 'latest'
    latest_path = settings.artifacts_dir / "summaries/latest/meta_portfolio_report.md"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import shutil

        shutil.copy(report_path, latest_path)
    except Exception as e:
        logger.warning(f"Failed to update latest report: {e}")

    logger.info(f"✅ Meta-Portfolio Pipeline COMPLETE: {meta_profile}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")
    parser.add_argument("--profiles", help="Comma-separated risk profiles to process")
    parser.add_argument("--execute-sleeves", action="store_true", help="Execute sub-sleeves in parallel using Ray")
    parser.add_argument("--use-native-ray", action="store_true", help="Use Ray Native Actors instead of Subprocess")
    parser.add_argument("--run-id", help="Explicit Run ID")
    args = parser.parse_args()

    target_profs = args.profiles.split(",") if args.profiles else None
    run_meta_pipeline(args.profile, target_profs, execute_sleeves=args.execute_sleeves, use_native_ray=args.use_native_ray, run_id=args.run_id)
