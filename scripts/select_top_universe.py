import glob
import json
import logging
import os

import numpy as np

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
                if p.upper() in ["BINANCE", "BYBIT", "OKX", "BITGET", "NASDAQ", "NYSE", "AMEX", "CME", "FOREX", "US", "BOND"]:
                    exchange = p.upper()
                if p.upper() in ["SPOT", "PERP", "FUTURES", "STOCKS", "ETF", "BONDS"]:
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

        # 1. Composite Alpha Ranking
        # We rank within category to find the most 'characteristic' assets
        if items:
            # Extract metrics
            v_traded = np.array([x.get("Value.Traded", 0) or 0 for x in items])
            adx = np.array([x.get("ADX", 0) or 0 for x in items])
            vol = np.array([x.get("Volatility.D", 0) or 0 for x in items])

            def norm(a):
                return (a - a.min()) / (a.max() - a.min() + 1e-9) if len(a) > 1 else np.array([1.0] * len(a))

            # Alpha Score favors: High Liquidity (40%), Strong Trend (40%), Active Participation (20%)
            alpha_scores = 0.4 * norm(v_traded) + 0.4 * norm(adx) + 0.2 * norm(vol)

            for i, item in enumerate(items):
                item["_alpha_score"] = float(alpha_scores[i])

            # Sort by Alpha Score
            items.sort(key=lambda x: x.get("_alpha_score", 0), reverse=True)

        top_10 = items[:10]
        logger.info(f"Category: {cat} - Selected {len(top_10)} from {len(items)} via Alpha Ranking")

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
                    "close": item.get("close", 0),
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
