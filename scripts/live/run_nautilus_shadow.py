import argparse
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

from tradingview_scraper.portfolio_engines.nautilus_live import NautilusLiveEngine
from tradingview_scraper.portfolio_engines.nautilus_live_strategy import LiveRebalanceStrategy, HAS_NAUTILUS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("nautilus_shadow_runner")


def run_shadow(profile: str, weights_file: str):
    if not HAS_NAUTILUS:
        logger.error("NautilusTrader not installed. Aborting.")
        sys.exit(1)

    logger.info(f"🚀 Starting Nautilus Shadow Mode for profile: {profile}")
    logger.info(f"Watching weights file: {weights_file}")

    # 1. Initialize Engine
    engine = NautilusLiveEngine(venue="BINANCE", mode="SHADOW")
    node = engine.build()

    if not node:
        logger.error("Failed to build Nautilus node.")
        sys.exit(1)

    # 2. Add Strategy
    strategy_config = {
        "weights_file": weights_file,
        "venue_str": "BINANCE",
    }

    # In Nautilus, we add strategy via node.add_strategy
    from nautilus_trader.config import StrategyConfig

    class LiveRebalanceStrategyConfig(StrategyConfig):
        weights_file: str
        venue_str: str

    config = LiveRebalanceStrategyConfig(name="live-rebalance-shadow", weights_file=weights_file, venue_str="BINANCE")

    node.add_strategy(LiveRebalanceStrategy, config)

    # 3. Handle Signals
    def signal_handler(sig, frame):
        logger.info("Stopping Nautilus node...")
        node.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. Run
    logger.info("Running Nautilus node (Press Ctrl+C to stop)")
    node.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nautilus Shadow Mode Runner")
    parser.add_argument("--profile", default="institutional_etf", help="Optimization profile")
    parser.add_argument("--weights", default="data/lakehouse/portfolio_optimized_v3.json", help="Path to weights file")
    args = parser.parse_args()

    # Pre-check weights file
    if not os.path.exists(args.weights):
        logger.error(f"Weights file not found: {args.weights}")
        sys.exit(1)

    run_shadow(args.profile, args.weights)
