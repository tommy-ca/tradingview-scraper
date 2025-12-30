import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("recover_universe")


def recover():
    logger.info("Starting recovery pass for all assets...")

    # 1. Run targeted repair for all symbols using --type all
    logger.info("Executing comprehensive gap repair (multi-pass)...")
    # Pass 1: standard repair
    subprocess.run(["uv", "run", "scripts/repair_portfolio_gaps.py", "--type", "all", "--max-fills", "10"])

    # Pass 2: high intensity repair for anything still degraded
    # We load candidates to know what to repair
    logger.info("Refreshing returns matrix (aligned 200 days)...")
    subprocess.run(["make", "prep", "BACKFILL=1", "GAPFILL=1", "LOOKBACK=200", "BATCH=2"])

    # 3. Final validation
    logger.info("Performing final audit check...")
    res = subprocess.run(["make", "audit-health"])
    if res.returncode != 0:
        logger.error("Recovery failed to resolve all critical data health issues.")
        # We don't exit(1) here if we want the pipeline to attempt a best-effort,
        # but Step 8 in Makefile will catch it.


if __name__ == "__main__":
    recover()
