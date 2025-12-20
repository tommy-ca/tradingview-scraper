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
        payload = json.load(f)

    if isinstance(payload, dict):
        symbols = payload.get("data", [])
    else:
        symbols = payload

    count = len(symbols)

    logging.info(f"--- Verifying {os.path.basename(file_path)} ---")
    logging.info(f"Count: {count}/{target_count}")

    if count == 0:
        logging.warning("Universe is empty.")
        return True

    all_ok = True

    # 1. Liquidity check
    low_liquidity = [s["symbol"] for s in symbols if s.get("Value.Traded", 0) < min_value_traded]
    if low_liquidity:
        logging.error(f"  Found {len(low_liquidity)} symbols below liquidity floor {min_value_traded}: {low_liquidity[:5]}")
        all_ok = False

    # 2. Market Cap Floor check (Guard B)
    low_cap = []
    suspicious = []
    for i, s in enumerate(symbols):
        calc = s.get("market_cap_calc") or 0
        ext = s.get("market_cap_external") or 0
        if max(calc, ext) < market_cap_floor:
            low_cap.append(s["symbol"])

        # junk check: top assets should have external market cap ranking
        if i < 10 and not s.get("market_cap_external"):
            suspicious.append(s["symbol"])

    if low_cap:
        logging.error(f"  Found {len(low_cap)} symbols below market cap floor {market_cap_floor}: {low_cap[:5]}...")
        all_ok = False

    if suspicious:
        logging.warning(f"  Found {len(suspicious)} high-volume symbols missing external market cap data: {suspicious}")

    if all_ok:
        logging.info("  Quality check passed.")
    return all_ok


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
