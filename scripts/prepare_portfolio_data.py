import json
import logging
import math
import os
import threading
import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta

import pandas as pd

from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_data_prep")


def prepare_portfolio_universe():
    """
    Preparation Stage.
    Loads historical data for candidates sanctioned by the Discovery Consolidator.
    Strictly follows the portfolio_candidates_raw.json manifest.
    """
    # 1. Load sanctioned candidates
    preselected_file = os.getenv("CANDIDATES_FILE", "data/lakehouse/portfolio_candidates_raw.json")
    if not os.path.exists(preselected_file):
        logger.error(f"Sanctioned candidate manifest missing: {preselected_file}")
        return

    logger.info(f"Loading sanctioned candidates from {preselected_file}")
    with open(preselected_file, "r") as f:
        universe = json.load(f)

    if not universe:
        logger.error("No candidates found in manifest.")
        return

    # 2. Benchmark Enforcement
    # Always ensure benchmarks are in candidates and LONG
    from tradingview_scraper.settings import get_settings

    settings = get_settings()

    universe_symbols = {c["symbol"] for c in universe}
    for b_sym in settings.benchmark_symbols:
        if b_sym not in universe_symbols:
            logger.info("Ensuring benchmark symbol %s is LONG.", b_sym)
            universe.append(
                {
                    "symbol": b_sym,
                    "description": f"Benchmark ({b_sym})",
                    "sector": "INDEX",
                    "market": "BENCHMARK",
                    "asset_class": "BENCHMARK",
                    "identity": b_sym,
                    "direction": "LONG",
                    "is_baseline": True,
                    "value_traded": 1e12,
                }
            )

    logger.info(f"Portfolio Universe: {len(universe)} symbols.")

    # 3. Fetch Historical Data
    loader = PersistentDataLoader()
    end_date = datetime.now()
    lookback_days = int(os.getenv("PORTFOLIO_LOOKBACK_DAYS", "120"))
    start_date = end_date - timedelta(days=lookback_days)

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

        # 1. Selective Sync Check
        is_stale = True
        parquet_path = f"data/lakehouse/{symbol.replace(':', '_')}_1d.parquet"
        if os.path.exists(parquet_path):
            mtime = os.path.getmtime(parquet_path)
            # If updated in the last 12 hours, consider fresh for Daily data
            if (time.time() - mtime) < (12 * 3600):
                is_stale = False

        force_sync = os.getenv("PORTFOLIO_FORCE_SYNC", "0") == "1"

        if (os.getenv("PORTFOLIO_BACKFILL", "0") == "1") and (is_stale or force_sync):
            try:
                bf_depth = min(lookback_days + 20, 500)
                logger.info(f"Backfilling {symbol} (depth={bf_depth})...")
                run_with_retry(lambda: local_loader.sync(symbol, interval="1d", depth=bf_depth, total_timeout=180), f"Backfill {symbol}")
            except Exception as e:
                logger.error(f"Backfill failed for {symbol}: {e}")

        if (os.getenv("PORTFOLIO_GAPFILL", "0") == "1") and (is_stale or force_sync):
            try:
                logger.info(f"Gap filling {symbol} (max_depth=500)...")
                run_with_retry(lambda: local_loader.repair(symbol, interval="1d", max_depth=500, max_fills=20, max_time=120, total_timeout=120), f"Gap fill {symbol}")
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
            if candidate.get("direction") == "SHORT":
                returns = -returns

            with lock:
                price_data[symbol] = returns
                alpha_meta[symbol] = {
                    "description": candidate.get("description", "N/A"),
                    "sector": candidate.get("sector", "N/A"),
                    "adx": candidate.get("adx", 0),
                    "close": candidate.get("close", 0),
                    "atr": candidate.get("atr", 0),
                    "value_traded": candidate.get("value_traded", 0),
                    "direction": candidate.get("direction", "LONG"),
                    "market": candidate.get("market", "UNKNOWN"),
                    "identity": candidate.get("identity", symbol),
                }
        except Exception as e:
            skipped_errors.append(symbol)
            logger.error(f"Failed to load {symbol}: {e}")

    total_batches = math.ceil(len(universe) / batch_size) if batch_size > 0 else 1

    for batch_idx in range(total_batches):
        batch = universe[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        logger.info("Processing batch %s/%s (%s symbols)", batch_idx + 1, total_batches, len(batch))
        with ThreadPoolExecutor(max_workers=max(1, batch_size)) as executor:
            futures = [executor.submit(fetch_and_store, c) for c in batch]
            per_symbol_timeout = 300
            batch_timeout = len(batch) * per_symbol_timeout
            done, not_done = wait(futures, timeout=batch_timeout, return_when=ALL_COMPLETED)

            for fut in done:
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"Worker error: {e}")

            if not_done:
                logger.error(f"Batch timed out. {len(not_done)} tasks incomplete.")

    # 4. Aligned Matrix Creation
    all_dates = sorted(set().union(*(rets.index for rets in price_data.values())))
    returns_df = pd.DataFrame(index=pd.Index(all_dates))

    for symbol, rets in price_data.items():
        returns_df[symbol] = rets

    # Aligned holding model (market closed = 0 returns)
    returns_df = returns_df.fillna(0.0)

    # Drop zero-variance noise
    zero_vars = [str(c) for c, v in returns_df.var().items() if v == 0]
    if zero_vars:
        returns_df = returns_df.drop(columns=zero_vars)
        logger.info("Dropped zero-variance symbols: %s", ", ".join(zero_vars))

    # Post-load Deduplication (Optional safety pass)
    if os.getenv("PORTFOLIO_DEDUPE_BASE", "0") == "1":
        deduped_cols = []
        seen_idents = set()
        for col in returns_df.columns:
            ident = alpha_meta.get(col, {}).get("identity", col)
            if ident in seen_idents:
                continue
            seen_idents.add(ident)
            deduped_cols.append(col)
        if len(deduped_cols) != len(returns_df.columns):
            logger.info("Dedupe by identity kept %d of %d symbols", len(deduped_cols), len(returns_df.columns))
            returns_df = returns_df[deduped_cols]

    alpha_meta = {s: alpha_meta[s] for s in returns_df.columns if s in alpha_meta}

    logger.info(f"Returns matrix created: {returns_df.shape}")
    returns_df.to_pickle("data/lakehouse/portfolio_returns.pkl")
    with open("data/lakehouse/portfolio_meta.json", "w") as f:
        json.dump(alpha_meta, f, indent=2)

    print("\n" + "=" * 50)
    print("PORTFOLIO UNIVERSE PREPARED")
    print("=" * 50)
    print(f"Matrix Shape : {returns_df.shape}")
    print(f"Symbols      : {', '.join(returns_df.columns)}")


if __name__ == "__main__":
    prepare_portfolio_universe()
