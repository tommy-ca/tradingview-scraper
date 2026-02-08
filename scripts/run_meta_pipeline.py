import argparse
import logging
from pathlib import Path
from tradingview_scraper.backtest.engine import BacktestEngine
from tradingview_scraper.settings import set_active_settings, TradingViewScraperSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run Meta Pipeline (Fractal)")
    parser.add_argument("--profile", help="Settings profile (e.g. meta_production)", default="meta_production")
    parser.add_argument("--manifest", help="Manifest path", default="configs/manifest.json")
    parser.add_argument("--run-id", help="Explicit run ID")
    args = parser.parse_args()

    # Bootstrap settings
    settings = TradingViewScraperSettings(profile=args.profile, manifest_path=Path(args.manifest), run_id=args.run_id)
    set_active_settings(settings)

    logger.info(f"Starting Meta Pipeline | Profile: {settings.profile} | RunID: {settings.run_id}")

    # Initialize Engine
    engine = BacktestEngine()
    engine.load_data()

    # Run Tournament (Meta mode handles recursion via BacktestEngine logic)
    engine.run_tournament(mode="meta")


if __name__ == "__main__":
    main()
