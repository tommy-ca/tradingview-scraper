import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("recover_universe")


def recover():
    logger.info("Starting recovery pass for all assets...")

    # 1. Run targeted repair for all symbols using --type all
    logger.info("Executing comprehensive gap repair...")
    subprocess.run(["uv", "run", "scripts/repair_portfolio_gaps.py", "--type", "all", "--max-fills", "10"])

    # 2. Re-run preparation to ensure matrix alignment
    logger.info("Refreshing returns matrix (aligned 200 days)...")
    subprocess.run(["make", "prep", "BACKFILL=1", "GAPFILL=1", "LOOKBACK=200", "BATCH=2"])

    # 3. Final validation
    logger.info("Performing final audit...")
    subprocess.run(["make", "validate"])


if __name__ == "__main__":
    recover()
