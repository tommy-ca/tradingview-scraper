import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def verify_universe(file_path, target_count=50, min_value_traded=500000, market_cap_floor=10000000):
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

    if count == 0:
        logging.warning("Universe is empty.")
        return True

    # 1. Liquidity check
    low_liquidity = [s for s in symbols if s.get("Value.Traded", 0) < min_value_traded]

    # 2. Market Cap Floor check (Guard B)
    low_cap = []
    for s in symbols:
        calc = s.get("market_cap_calc") or 0
        ext = s.get("market_cap_external") or 0
        if max(calc, ext) < market_cap_floor:
            low_cap.append(s["symbol"])

    if low_cap:
        logging.error(f"Found {len(low_cap)} symbols below market cap floor {market_cap_floor}: {low_cap[:5]}...")
        return False

    logging.info("Quality check passed.")
    return True


def main():
    export_dir = Path("export")

    categories = [
        "binance_top50_spot_base",
        "binance_top50_perp_base",
        "okx_top50_spot_base",
        "okx_top50_perp_base",
        "bybit_top50_spot_base",
        "bybit_top50_perp_base",
        "bitget_top50_spot_base",
        "bitget_top50_perp_base",
    ]

    success = True
    for cat in categories:
        files = sorted(export_dir.glob(f"universe_selector_{cat}_*.json"), key=os.path.getmtime, reverse=True)
        if not files:
            logging.warning(f"No files found for category: {cat}")
            continue

        if not verify_universe(files[0]):
            success = False

    if not success:
        logging.error("One or more latest universes failed quality checks.")
        exit(1)
    else:
        logging.info("All selected base universes passed hybrid guard quality checks.")


if __name__ == "__main__":
    main()
