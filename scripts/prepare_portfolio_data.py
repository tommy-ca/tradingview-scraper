import hashlib
import json
import logging
import math
import os
import threading
import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta

import pandas as pd

from tradingview_scraper.settings import get_settings
from tradingview_scraper.symbols.stream.metadata import DataProfile, get_symbol_profile
from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_data_prep")


def prepare_portfolio_universe():
    """
    Preparation Stage.
    Loads historical data for candidates sanctioned by the Discovery Consolidator.
    Strictly follows the portfolio_candidates_raw.json manifest.
    """

    active_settings = get_settings()
    run_dir = active_settings.prepare_summaries_run_dir()
    ledger = AuditLedger(run_dir) if active_settings.features.feat_audit_ledger else None

    # 1. Load sanctioned candidates
    preselected_file = os.getenv("CANDIDATES_FILE", "data/lakehouse/portfolio_candidates.json")
    if not os.path.exists(preselected_file):
        logger.warning(f"Sanctioned candidate manifest missing: {preselected_file}. Falling back to raw manifest.")
        preselected_file = "data/lakehouse/portfolio_candidates_raw.json"

    if not os.path.exists(preselected_file):
        logger.error("No candidate manifest found.")
        return

    logger.info(f"Loading candidates from {preselected_file}")
    with open(preselected_file, "r") as f:
        universe = json.load(f)

    if not universe:
        logger.error("No candidates found in manifest.")
        return

    lookback_env = os.getenv("PORTFOLIO_LOOKBACK_DAYS")
    fallback_lookback = os.getenv("LOOKBACK")
    if lookback_env:
        lookback_days = int(lookback_env)
    elif fallback_lookback:
        lookback_days = int(fallback_lookback)
    else:
        lookback_days = int(active_settings.resolve_portfolio_lookback_days())

    if ledger:
        u_hash = hashlib.sha256(json.dumps(universe, sort_keys=True).encode()).hexdigest()
        ledger.record_intent(
            step="data_prep",
            params={"lookback_days": lookback_days},
            input_hashes={"candidates_manifest": u_hash},
        )

    # 2. Benchmark Enforcement
    universe_symbols = {c["symbol"] for c in universe}
    for b_sym in active_settings.benchmark_symbols:
        if b_sym not in universe_symbols:
            universe.append({"symbol": b_sym, "direction": "LONG", "is_benchmark": True})

    logger.info(f"Portfolio Universe: {len(universe)} symbols.")

    # 3. Fetch Historical Data
    loader = PersistentDataLoader()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    price_data = {}
    alpha_meta = {}
    lock = threading.Lock()
    jwt_token = os.getenv("TRADINGVIEW_JWT_TOKEN", "unauthorized_user_token")
    batch_env = os.getenv("PORTFOLIO_BATCH_SIZE")
    batch_size = int(batch_env) if batch_env else int(active_settings.portfolio_batch_size)
    backfill_env = os.getenv("PORTFOLIO_BACKFILL")
    gapfill_env = os.getenv("PORTFOLIO_GAPFILL")
    force_env = os.getenv("PORTFOLIO_FORCE_SYNC")
    do_backfill = backfill_env == "1" if backfill_env is not None else bool(active_settings.portfolio_backfill)
    do_gapfill = gapfill_env == "1" if gapfill_env is not None else bool(active_settings.portfolio_gapfill)
    force_sync = force_env == "1" if force_env is not None else bool(active_settings.portfolio_force_sync)

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

        if do_backfill and (is_stale or force_sync):
            try:
                # Deep Sync: request up to 1000 candles to ensure full coverage of 2025 and beyond
                bf_depth = max(lookback_days + 50, 1000)
                logger.info(f"Backfilling {symbol} (depth={bf_depth})...")
                run_with_retry(lambda: local_loader.sync(symbol, interval="1d", depth=bf_depth, total_timeout=300), f"Backfill {symbol}")
            except Exception as e:
                logger.error(f"Backfill failed for {symbol}: {e}")

        if do_gapfill and (is_stale or force_sync):
            try:
                logger.info(f"Gap filling {symbol} (max_depth=1000)...")
                run_with_retry(lambda: local_loader.repair(symbol, interval="1d", max_depth=1000, max_fills=20, max_time=180, total_timeout=180), f"Gap fill {symbol}")
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
                    "is_benchmark": candidate.get("is_benchmark", False),
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

    # Drop rows where ALL non-crypto assets are missing (e.g., weekends for TradFi)
    profiles = {symbol: get_symbol_profile(symbol) for symbol in returns_df.columns}
    tradfi_cols = [s for s, p in profiles.items() if p != DataProfile.CRYPTO]
    if tradfi_cols:
        tradfi_all_nan = returns_df[tradfi_cols].isna().all(axis=1)
        returns_df = returns_df.loc[~tradfi_all_nan]

    # Drop zero-variance noise
    variances = returns_df.var()
    zero_vars = []
    if not isinstance(variances, (float, int)):
        zero_vars = [str(c) for c, v in variances.items() if v == 0]

    if zero_vars:
        returns_df = returns_df.drop(columns=zero_vars)
        logger.info("Dropped zero-variance symbols: %s", ", ".join(zero_vars))

    # Apply History Floor (min_days_floor)
    # Only enforce if we are fetching at least that much data (High Integrity pass)
    min_days = int(active_settings.min_days_floor)
    if min_days > 0 and lookback_days >= min_days:
        counts = returns_df.count()
        short_history = [str(c) for c, v in counts.items() if v < min_days]
        if short_history:
            returns_df = returns_df.drop(columns=short_history)
            logger.info("Dropped %d symbols due to insufficient secular history (< %d days): %s", len(short_history), min_days, ", ".join(short_history))

    # Post-load Deduplication (Optional safety pass)
    dedupe_env = os.getenv("PORTFOLIO_DEDUPE_BASE")
    do_dedupe = dedupe_env == "1" if dedupe_env is not None else bool(active_settings.portfolio_dedupe_base)
    if do_dedupe:
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

    returns_path = os.getenv("PORTFOLIO_RETURNS_PATH", "data/lakehouse/portfolio_returns.pkl")
    meta_path = os.getenv("PORTFOLIO_META_PATH", "data/lakehouse/portfolio_meta.json")

    logger.info(f"Returns matrix created: {returns_df.shape}")
    logger.info(f"Writing returns matrix to: {returns_path}")
    returns_df.to_pickle(returns_path)
    with open(meta_path, "w") as f:
        json.dump(alpha_meta, f, indent=2)

    if ledger:
        ledger.record_outcome(
            step="data_prep",
            status="success",
            output_hashes={"returns_matrix": get_df_hash(returns_df)},
            metrics={"shape": returns_df.shape, "n_symbols": len(returns_df.columns), "returns_path": returns_path, "meta_path": meta_path},
        )

    print("\n" + "=" * 50)
    print("PORTFOLIO UNIVERSE PREPARED")
    print("=" * 50)
    print(f"Matrix Shape : {returns_df.shape}")
    print(f"Symbols      : {', '.join(returns_df.columns)}")


if __name__ == "__main__":
    prepare_portfolio_universe()
