import glob
import json
import logging
import os

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("select_top_universe")


def select_top_universe(mode: str = "raw"):
    files = glob.glob("export/universe_selector_*.json")

    categories = {}

    for f in files:
        # Determine category from filename
        parts = os.path.basename(f).split("_")
        try:
            # remove universe, selector, date
            clean = [p for p in parts if p not in ["universe", "selector"] and not p[0].isdigit()]

            # Simple heuristic: Exchange + Type
            exchange = "UNKNOWN"
            mtype = "UNKNOWN"

            for p in clean:
                if p.upper() in ["BINANCE", "BYBIT", "OKX", "BITGET", "NASDAQ", "NYSE", "AMEX", "CME", "FOREX", "US", "BOND", "OANDA", "THINKMARKETS"]:
                    exchange = p.upper()
                if p.upper() in ["SPOT", "PERP", "FUTURES", "STOCKS", "ETF", "BONDS", "CFD"]:
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

                if not items:
                    items = []

                # Enrich with direction and scan file name for tracking
                file_direction = "SHORT" if "_short" in os.path.basename(f).lower() else "LONG"
                for i in items:
                    if isinstance(i, dict):
                        i["_direction"] = file_direction
                        i["_category"] = category

                categories[category].extend(items)
        except Exception as e:
            logger.error(f"Error reading {f}: {e}")

    final_universe = []

    for cat, items in categories.items():
        # Deduplicate by symbol
        unique_items = {}
        for item in items:
            if isinstance(item, dict) and "symbol" in item:
                unique_items[item["symbol"]] = item

        items = list(unique_items.values())

        # Always calculate Alpha Ranking to allow truncation in 'raw' mode too
        if items:
            v_traded = np.array([float(x.get("Value.Traded", 0) or 0) for x in items])
            adx = np.array([float(x.get("ADX", 0) or 0) for x in items])
            vol = np.array([float(x.get("Volatility.D", 0) or 0) for x in items])

            def norm(a):
                return (a - a.min()) / (a.max() - a.min() + 1e-9) if len(a) > 1 else np.array([1.0] * len(a))

            # Alpha Score favors: High Liquidity (40%), Strong Trend (40%), Active Participation (20%)
            alpha_scores = 0.4 * norm(v_traded) + 0.4 * norm(adx) + 0.2 * norm(vol)

            for i, item in enumerate(items):
                item["_alpha_score"] = float(alpha_scores[i])

            items.sort(key=lambda x: x.get("_alpha_score", 0), reverse=True)

        if mode == "top":
            limit = int(os.getenv("UNIVERSE_TOP_N", "20"))
            items = items[:limit]
            logger.info(f"Category: {cat} - Selected Top {len(items)} via Alpha Ranking")
        elif mode == "raw":
            # Apply a loose truncation to prevent massive bloat (e.g. Top 30)
            raw_limit = int(os.getenv("RAW_TOP_N", "30"))
            if len(items) > raw_limit:
                items = items[:raw_limit]
                logger.info(f"Category: {cat} - Truncated raw pool to Top {raw_limit} via Alpha Ranking")

        for item in items:
            final_universe.append(
                {
                    "symbol": item["symbol"],
                    "description": item.get("description", "N/A"),
                    "sector": item.get("sector", "N/A"),
                    "market": item.get("_category", cat),
                    "close": item.get("close", 0),
                    "value_traded": item.get("Value.Traded", 0),
                    "adx": item.get("ADX", 0),
                    "atr": item.get("ATR", 0),
                    "direction": item.get("_direction", "LONG"),
                }
            )

    output_file = "data/lakehouse/portfolio_candidates.json"
    if mode == "raw":
        output_file = "data/lakehouse/portfolio_candidates_raw.json"

    with open(output_file, "w") as f:
        json.dump(final_universe, f, indent=2)

    logger.info(f"Saved {len(final_universe)} candidates to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["raw", "top"], default="raw")
    args = parser.parse_args()
    select_top_universe(mode=args.mode)
