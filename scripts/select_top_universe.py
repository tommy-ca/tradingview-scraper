import glob
import json
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("select_top_universe")


def select_top_universe():
    files = glob.glob("export/universe_selector_*.json")

    categories = {}

    for f in files:
        # Determine category from filename
        parts = os.path.basename(f).split("_")
        try:
            # remove universe, selector, date
            clean = [p for p in parts if p not in ["universe", "selector"] and not p[0].isdigit()]

            # Simple heuristic: Exchange + Type
            # If we have binance, perp/spot
            exchange = "UNKNOWN"
            mtype = "UNKNOWN"

            for p in clean:
                if p.upper() in ["BINANCE", "BYBIT", "OKX", "BITGET", "NASDAQ", "NYSE", "AMEX", "CME", "FOREX", "US"]:
                    exchange = p.upper()
                if p.upper() in ["SPOT", "PERP", "FUTURES", "STOCKS", "ETF"]:
                    mtype = p.upper()

            category = f"{exchange}_{mtype}"

        except Exception:
            category = "UNKNOWN"

        if category not in categories:
            categories[category] = []

        try:
            with open(f, "r") as j:
                raw_data = json.load(j)

                items = []
                if isinstance(raw_data, dict):
                    items = raw_data.get("data", [])
                elif isinstance(raw_data, list):
                    items = raw_data

                # Check if items is None or invalid
                if not items:
                    items = []

                # Enrich with direction
                file_direction = "SHORT" if "_short" in os.path.basename(f).lower() else "LONG"
                for i in items:
                    if isinstance(i, dict):
                        i["_direction"] = file_direction

                categories[category].extend(items)
        except Exception as e:
            logger.error(f"Error reading {f}: {e}")

    final_universe = []

    for cat, items in categories.items():
        # Deduplicate
        unique_items = {}
        for item in items:
            if isinstance(item, dict) and "symbol" in item:
                unique_items[item["symbol"]] = item

        items = list(unique_items.values())

        # Sort by Value.Traded
        items.sort(key=lambda x: x.get("Value.Traded", 0) or 0, reverse=True)

        top_10 = items[:10]
        logger.info(f"Category: {cat} - Selected {len(top_10)} from {len(items)}")

        for item in top_10:
            # Determine direction from filename stored in 'market' or pass it down?
            # 'market' is 'category' which is e.g. BINANCE_SPOT
            # We lost the filename context in 'categories[category]'.
            # We should probably store direction in the item during parsing.

            direction = item.get("_direction", "LONG")

            final_universe.append(
                {
                    "symbol": item["symbol"],
                    "description": item.get("description", "N/A"),
                    "sector": item.get("sector", "N/A"),
                    "market": cat,
                    "value_traded": item.get("Value.Traded", 0),
                    "adx": item.get("ADX", 0),
                    "atr": item.get("ATR", 0),
                    "direction": direction,
                }
            )

    with open("data/lakehouse/portfolio_candidates.json", "w") as f:
        json.dump(final_universe, f, indent=2)

    logger.info(f"Saved {len(final_universe)} candidates to data/lakehouse/portfolio_candidates.json")


if __name__ == "__main__":
    select_top_universe()
