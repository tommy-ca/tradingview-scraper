import argparse
import json
import logging
import os
import time

from tradingview_scraper.symbols.stream.metadata import DataProfile, get_symbol_profile
from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("repair_gaps")


def repair_gaps():
    parser = argparse.ArgumentParser(description="Repair data gaps in the portfolio lakehouse.")
    parser.add_argument("--type", type=str, choices=["crypto", "trad", "all"], default="all", help="Asset type to repair")
    parser.add_argument("--symbol", type=str, help="Specific symbol to repair")
    parser.add_argument("--max-fills", type=int, default=10, help="Max gaps to fill per symbol")
    parser.add_argument("--max-time", type=int, default=120, help="Max seconds per symbol repair")
    parser.add_argument("--timeout", type=int, default=60, help="Total timeout per API call")
    args = parser.parse_args()

    candidates = []
    # CR-831: Workspace Isolation
    # Prioritize CANDIDATES_SELECTED, then CANDIDATES_RAW, then legacy paths
    from tradingview_scraper.settings import get_settings

    run_dir = get_settings().prepare_summaries_run_dir()

    candidates_files = []

    # Highest priority: Env var
    env_file = os.getenv("CANDIDATES_FILE") or os.getenv("CANDIDATES_SELECTED") or os.getenv("CANDIDATES_RAW")
    if env_file:
        candidates_files.append(env_file)

    # Second priority: Run-specific workspace
    candidates_files.append(str(run_dir / "data" / "portfolio_candidates.json"))
    candidates_files.append(str(run_dir / "data" / "portfolio_candidates_raw.json"))

    # Final priority: Shared lakehouse
    candidates_files.extend(["data/lakehouse/portfolio_candidates.json", "data/lakehouse/portfolio_candidates_raw.json"])

    for cf in candidates_files:
        if os.path.exists(cf):
            try:
                with open(cf, "r") as f:
                    candidates = json.load(f)
                logger.info(f"Loaded {len(candidates)} candidates from {cf}")
                break
            except Exception as e:
                logger.error(f"Failed to load {cf}: {e}")

    if not candidates:
        logger.error("No candidates file found.")
        return

    loader = PersistentDataLoader()
    total_candles_filled = 0
    symbols_with_gaps = 0
    processed_count = 0

    # Filter candidates based on args
    targets = []
    for c in candidates:
        symbol = c["symbol"]
        if args.symbol and symbol != args.symbol:
            continue

        meta = loader.catalog.get_instrument(symbol)
        profile = get_symbol_profile(symbol, meta)

        is_crypto = profile == DataProfile.CRYPTO

        if args.type == "crypto" and not is_crypto:
            continue
        if args.type == "trad" and is_crypto:
            continue

        targets.append((symbol, profile))

    logger.info(f"Starting repair for {len(targets)} symbols (Type filter: {args.type})")

    for symbol, profile in targets:
        processed_count += 1
        logger.info(f"[{processed_count}/{len(targets)}] Checking gaps for {symbol} ({profile.value})...")

        # Exponential backoff for rate limits
        retries = 2
        for attempt in range(retries + 1):
            try:
                # Pass profile to repair for market-aware detection
                filled = loader.repair(symbol, interval="1d", max_depth=500, max_fills=args.max_fills, max_time=args.max_time, total_timeout=args.timeout, profile=profile)
                if filled > 0:
                    total_candles_filled += filled
                    symbols_with_gaps += 1
                break  # Success
            except Exception as e:
                is_429 = "429" in str(e)
                if is_429 and attempt < retries:
                    sleep_time = 30 * (attempt + 1)
                    logger.warning(f"  Rate limit hit for {symbol}. Retrying in {sleep_time}s... ({attempt + 1}/{retries})")
                    time.sleep(sleep_time)
                    continue
                logger.error(f"Failed to repair gaps for {symbol}: {e}")
                break

    logger.info("=" * 50)
    logger.info("REPAIR SUMMARY")
    logger.info("=" * 50)
    logger.info(f"Symbols targeted  : {len(targets)}")
    logger.info(f"Symbols with gaps : {symbols_with_gaps}")
    logger.info(f"Total candles filled: {total_candles_filled}")
    logger.info("=" * 50)


if __name__ == "__main__":
    repair_gaps()
