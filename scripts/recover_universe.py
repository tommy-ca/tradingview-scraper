import logging
import os
import subprocess
import sys

# Add the project root to the path so we can import internal modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("recover_universe")


def recover():
    logger.info("Starting recovery pass for all assets...")

    settings = get_settings()
    run_dir = settings.prepare_summaries_run_dir()
    ledger = None
    if settings.features.feat_audit_ledger:
        ledger = AuditLedger(run_dir)

    if ledger:
        ledger.record_intent(step="recovery_internals", params={"strategy": "intensive_repair"}, input_hashes={})

    # 1. Run targeted repair for all symbols using --type all
    logger.info("Executing comprehensive gap repair (multi-pass)...")
    # Pass 1: standard repair
    subprocess.run(["uv", "run", "scripts/repair_portfolio_gaps.py", "--type", "all", "--max-fills", "15"])

    # Pass 2: high intensity repair for anything still degraded
    logger.info("Refreshing aligned returns matrix...")
    lookback = os.getenv("LOOKBACK", "200")
    subprocess.run(["make", "prep", "BACKFILL=1", "GAPFILL=1", f"LOOKBACK={lookback}", "BATCH=2"])

    if ledger:
        ledger.record_outcome(step="recovery_internals", status="success", output_hashes={}, metrics={"strategy": "intensive_repair"})

    logger.info("Recovery sequence finished.")


if __name__ == "__main__":
    recover()
