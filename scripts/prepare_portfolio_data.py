import glob
import json
import logging
import math
import os
import threading
import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from typing import List

import pandas as pd

from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_data_prep")


def prepare_portfolio_universe():
    # 1. Identify candidates
    candidates = []

    # Check for pre-selected candidates file first
    preselected_file = "data/lakehouse/portfolio_candidates.json"
    if os.path.exists(preselected_file):
        logger.info(f"Loading candidates from {preselected_file}")
        with open(preselected_file, "r") as f:
            candidates = json.load(f)
    else:
        # Fallback to scanning exports (Old behavior)
        files = glob.glob("export/universe_selector_*.json")
        # Filter for today's timestamp in filename (20251221) - Update to match current date or just take all recent?
        # Let's just take all for now if fallback is needed, or keep existing logic.
        # But since we generated candidates, we expect to use them.

        # files = [f for f in files if "20251221" in f] # OLD
        # Let's verify date dynamically if needed, but for now assuming candidates file exists.
        pass

    if not candidates:
        # 1. Identify candidates from latest exports (Original Logic as backup)
        files = glob.glob("export/universe_selector_*.json")
        today_str = datetime.now().strftime("%Y%m%d")
        files = [f for f in files if today_str in f]

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
                        # check 'all' flag - NO, we want raw universe for portfolio usually?
                        # Or do we only want those passing filter?
                        # The candidates file we built already filtered top 10.
                        # Here we probably want passing ones.
                        if item.get("passes", {}).get("all", False):
                            direction = "LONG" if "_long" in f.lower() or ("short" not in f.lower() and "mr" not in f.lower()) else "SHORT"
                            if "_short" in f.lower():
                                direction = "SHORT"

                            candidates.append(
                                {"symbol": item["symbol"], "direction": direction, "market": item.get("type", "unknown"), "adx": item.get("ADX", 0), "value_traded": item.get("Value.Traded", 0)}
                            )
                except Exception as e:
                    logger.error(f"  Error parsing {f}: {e}")
                    continue

    if not candidates:
        logger.error("No candidates found.")
        return

    # Deduplicate by symbol (taking first found direction and metadata)
    unique_candidates = {}
    for c in candidates:
        if c["symbol"] not in unique_candidates:
            unique_candidates[c["symbol"]] = c

    # Sort by value_traded descending to keep the most liquid first
    universe = sorted(unique_candidates.values(), key=lambda x: x.get("value_traded", 0), reverse=True)

    max_symbols = int(os.getenv("PORTFOLIO_MAX_SYMBOLS", "50"))
    if max_symbols > 0:
        universe = universe[:max_symbols]
    logger.info(f"Portfolio Universe: {len(universe)} symbols after limiting (max={max_symbols}).")

    # 2. Fetch Historical Data
    loader = PersistentDataLoader()
    end_date = datetime.now()
    lookback_days = int(os.getenv("PORTFOLIO_LOOKBACK_DAYS", "120"))
    start_date = end_date - timedelta(days=lookback_days)

    # We'll store returns and sidecar metadata here
    price_data = {}
    alpha_meta = {}
    lock = threading.Lock()
    jwt_token = os.getenv("TRADINGVIEW_JWT_TOKEN", "unauthorized_user_token")
    batch_size = int(os.getenv("PORTFOLIO_BATCH_SIZE", "1"))

    def run_with_retry(func, action: str, retries: int = 2, base_sleep: int = 10):
        """Retry helper to throttle on 429 errors."""
        for attempt in range(retries + 1):
            try:
                return func()
            except Exception as e:
                is_429 = "429" in str(e)
                if is_429 and attempt < retries:
                    sleep_for = base_sleep * (attempt + 1)
                    logger.warning(f"{action} hit 429; sleeping {sleep_for}s before retry ({attempt + 1}/{retries}).")
                    time.sleep(sleep_for)
                    continue
                raise

    skipped_empty = []
    skipped_errors = []

    def fetch_and_store(candidate):
        symbol = candidate["symbol"]
        local_loader = PersistentDataLoader(websocket_jwt_token=jwt_token)

        if os.getenv("PORTFOLIO_BACKFILL", "0") == "1":
            try:
                # Limit backfill depth to 250 days max to prevent large pulls / 429s
                bf_depth = min(lookback_days + 20, 250)
                logger.info(f"Backfilling {symbol} (depth={bf_depth})...")
                # Use a total timeout for backfill
                run_with_retry(lambda: local_loader.sync(symbol, interval="1d", depth=bf_depth, total_timeout=120), f"Backfill {symbol}")
            except Exception as e:
                logger.error(f"Backfill failed for {symbol}: {e}")

        if os.getenv("PORTFOLIO_GAPFILL", "0") == "1":
            try:
                logger.info(f"Gap filling {symbol} (max_depth=250)...")
                # max_time=60s, max_fills=3, total_timeout=60s per gap-fill call
                run_with_retry(lambda: local_loader.repair(symbol, interval="1d", max_depth=250, max_fills=3, max_time=60, total_timeout=60), f"Gap fill {symbol}")
            except Exception as e:
                logger.error(f"Gap fill failed for {symbol}: {e}")

        logger.info(f"Loading history for {symbol}...")
        try:
            df = local_loader.load(symbol, start_date, end_date, interval="1d")
            if df.empty:
                skipped_empty.append(symbol)
                return

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
            df = df.set_index("timestamp")["close"]

            returns = df.pct_change().dropna()
            if candidate["direction"] == "SHORT":
                returns = -returns

            with lock:
                price_data[symbol] = returns
                alpha_meta[symbol] = {
                    "adx": candidate.get("adx", 0),
                    "value_traded": candidate.get("value_traded", 0),
                    "direction": candidate.get("direction", "LONG"),
                }
        except Exception as e:
            skipped_errors.append(symbol)
            logger.error(f"Failed to load {symbol}: {e} Keys: {list(candidate.keys())}")

    total_batches = math.ceil(len(universe) / batch_size) if batch_size > 0 else 1

    for batch_idx in range(total_batches):
        batch = universe[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        logger.info(
            "Processing batch %s/%s (%s symbols) [batch_size=%s, lookback_days=%s]",
            batch_idx + 1,
            total_batches,
            len(batch),
            batch_size,
            lookback_days,
        )
        with ThreadPoolExecutor(max_workers=max(1, batch_size)) as executor:
            futures = [executor.submit(fetch_and_store, c) for c in batch]

            # Timeout per batch (e.g. 5 minutes per symbol)
            per_symbol_timeout = 300
            batch_timeout = len(batch) * per_symbol_timeout

            done, not_done = wait(futures, timeout=batch_timeout, return_when=ALL_COMPLETED)

            for fut in done:
                try:
                    fut.result()
                except Exception as e:  # pragma: no cover - already logged
                    logger.error(f"Worker error: {e}")

            if not_done:
                logger.error(f"Batch timed out after {batch_timeout}s. {len(not_done)} tasks incomplete (moving on).")

    # 3. Align and Save
    returns_df = pd.DataFrame(price_data)

    # Fill NaNs with 0.0 before filtering.
    # This handles weekend gaps for equities/futures without dropping the entire row.
    returns_df = returns_df.fillna(0.0)

    # Drop sparse columns based on min history fraction
    min_hist_frac = float(os.getenv("PORTFOLIO_MIN_HISTORY_FRAC", "0.2"))
    min_count = int(len(returns_df) * min_hist_frac) if len(returns_df) else 0
    before_cols = returns_df.shape[1]
    dropped_sparse = 0
    if min_count > 0:
        returns_df = returns_df.dropna(axis=1, thresh=min_count)
        dropped_sparse = before_cols - returns_df.shape[1]
    if dropped_sparse:
        logger.info("Dropped %d sparse symbols (min_history_frac=%.2f)", dropped_sparse, min_hist_frac)

    # Drop rows with any NaN to align dates
    returns_df = returns_df.dropna()

    # Drop zero-variance columns
    zero_vars: List[str] = []
    var = returns_df.var()
    if isinstance(var, pd.Series):
        zero_vars = [str(c) for c, v in var.items() if v == 0]
    if zero_vars:
        returns_df = returns_df.drop(columns=zero_vars)
        logger.info("Dropped zero-variance symbols: %s", ", ".join(zero_vars))

    # Optional dedupe by base symbol (e.g., across exchanges) when enabled
    if os.getenv("PORTFOLIO_DEDUPE_BASE", "0") == "1":
        deduped_cols = []
        seen_bases = set()
        for col in returns_df.columns:
            base = col.split(":")[-1]
            base = base.replace(".P", "").upper()
            if base in seen_bases:
                continue
            seen_bases.add(base)
            deduped_cols.append(col)
        if len(deduped_cols) != len(returns_df.columns):
            logger.info("Dedupe by base kept %d of %d symbols", len(deduped_cols), len(returns_df.columns))
            returns_df = returns_df[deduped_cols]

    # Filter alpha_meta to match aligned returns columns
    alpha_meta = {s: alpha_meta[s] for s in returns_df.columns if s in alpha_meta}

    # Coverage summary
    if skipped_empty:
        logger.info("Skipped empty symbols: %s", ", ".join(sorted(set(skipped_empty))))
    if skipped_errors:
        logger.info("Skipped errored symbols: %s", ", ".join(sorted(set(skipped_errors))))

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
