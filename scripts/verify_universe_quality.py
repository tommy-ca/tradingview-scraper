import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def verify_universe(file_path, target_count=50, min_value_traded=500000):
    """
    Verifies the quality of a universe JSON file.
    """
    if not os.path.exists(file_path):
        logging.error(f"File not found: {file_path}")
        return False

    with open(file_path, "r") as f:
        data = json.load(f)

    if isinstance(data, dict):
        symbols = data.get("data", [])
    else:
        symbols = data

    count = len(symbols)

    logging.info(f"--- Verifying {os.path.basename(file_path)} ---")
    logging.info(f"Count: {count}/{target_count}")

    low_liquidity = [s for s in symbols if s.get("Value.Traded", 0) < min_value_traded]
    # if low_liquidity:
    #    logging.warning(f"Found {len(low_liquidity)} symbols with Value.Traded < {min_value_traded}")

    if count < target_count * 0.8:  # Allow 20% margin
        logging.warning(f"Universe size is significantly below target ({count} < {target_count})")
        return False

    logging.info("Quality check passed.")
    return True


def main():
    export_dir = Path("export")
    # All files from today's run
    files = sorted(export_dir.glob("universe_selector_*.json"), key=os.path.getmtime, reverse=True)

    # Filter for base universe files from the most recent run (last hour)
    import time

    now = time.time()
    recent_files = [f for f in files if now - os.path.getmtime(f) < 3600]

    # Further filter for base universes (by excluding trend/momentum in name if possible,
    # or just looking at the ones we know we just generated)
    base_files = [f for f in recent_files if "_base" in f.name or "universe" in f.name]

    if not base_files:
        logging.error("No recent base universe files found in export/")
        exit(1)

    success = True
    for f in base_files:
        if not verify_universe(f):
            success = False

    if not success:
        logging.error("One or more universes failed quality checks.")
        exit(1)
    else:
        logging.info("All universes passed baseline quality checks.")


if __name__ == "__main__":
    main()
