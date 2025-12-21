import glob
import json
import logging
from datetime import datetime, timedelta

import pandas as pd

from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_data_prep")


def prepare_portfolio_universe():
    # 1. Identify candidates from latest exports (Today's run)
    files = glob.glob("export/universe_selector_*.json")
    # Filter for today's timestamp in filename (20251221)
    files = [f for f in files if "20251221" in f]

    candidates = []

    for f in files:
        logger.info(f"Reading file: {f}")
        with open(f, "r") as j:
            try:
                raw_data = json.load(j)
                # Handle both {'data': [...]} and [...] formats
                if isinstance(raw_data, dict):
                    items = raw_data.get("data", [])
                elif isinstance(raw_data, list):
                    items = raw_data
                else:
                    items = []

                logger.info(f"  Found {len(items)} items in {f}")
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    # check 'all' flag
                    if item.get("passes", {}).get("all", False):
                        direction = "LONG" if "_long" in f.lower() or ("short" not in f.lower() and "mr" not in f.lower()) else "SHORT"
                        # Special handling for trend_momentum which might be long by default
                        if "_short" in f.lower():
                            direction = "SHORT"

                        candidates.append(
                            {"symbol": item["symbol"], "direction": direction, "market": item.get("type", "unknown"), "adx": item.get("ADX", 0), "value_traded": item.get("Value.Traded", 0)}
                        )
            except Exception as e:
                logger.error(f"  Error parsing {f}: {e}")
                continue

    if not candidates:
        logger.error("No candidates found in exports. (Check if 'passes.all' is true in any JSON)")
        return

    # Deduplicate by symbol (taking first found direction and metadata)
    unique_candidates = {}
    for c in candidates:
        if c["symbol"] not in unique_candidates:
            unique_candidates[c["symbol"]] = c

    universe = list(unique_candidates.values())
    logger.info(f"Portfolio Universe: {len(universe)} symbols identified.")

    # 2. Fetch Historical Data
    loader = PersistentDataLoader()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)

    # We'll store returns and sidecar metadata here
    price_data = {}
    alpha_meta = {}

    for c in universe:
        symbol = c["symbol"]
        logger.info(f"Loading history for {symbol}...")
        try:
            # Load 1d data
            df = loader.load(symbol, start_date, end_date, interval="1d")
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
                df = df.set_index("timestamp")["close"]

                # Calculate returns
                returns = df.pct_change().dropna()

                # Apply Signal Inversion for SHORTS
                if c["direction"] == "SHORT":
                    returns = -returns

                price_data[symbol] = returns
                alpha_meta[symbol] = {"adx": c["adx"], "value_traded": c["value_traded"], "direction": c["direction"]}
        except Exception as e:
            logger.error(f"Failed to load {symbol}: {e}")

    # 3. Align and Save
    returns_df = pd.DataFrame(price_data).dropna()
    # Filter alpha_meta to match aligned returns columns
    alpha_meta = {s: alpha_meta[s] for s in returns_df.columns}

    logger.info(f"Returns matrix created: {returns_df.shape} (Dates x Symbols)")

    returns_df.to_pickle("data/lakehouse/portfolio_returns.pkl")
    with open("data/lakehouse/portfolio_meta.json", "w") as f:
        json.dump(alpha_meta, f, indent=2)

    print("\n" + "=" * 50)
    print("PORTFOLIO UNIVERSE PREPARED")
    print("=" * 50)
    print(f"Matrix Shape : {returns_df.shape}")
    print(f"Symbols      : {', '.join(returns_df.columns)}")
    print("Saved to data/lakehouse/portfolio_returns.pkl")


if __name__ == "__main__":
    prepare_portfolio_universe()
