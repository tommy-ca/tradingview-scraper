import json
import logging

from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("repair_gaps")


def repair_gaps():
    try:
        with open("data/lakehouse/portfolio_candidates.json", "r") as f:
            candidates = json.load(f)
    except FileNotFoundError:
        logger.error("portfolio_candidates.json not found")
        return

    loader = PersistentDataLoader()

    for c in candidates:
        symbol = c["symbol"]
        logger.info(f"Checking gaps for {symbol}...")
        loader.repair(symbol, interval="1d")


if __name__ == "__main__":
    repair_gaps()
