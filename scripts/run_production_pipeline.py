import argparse
import logging
from pathlib import Path
from tradingview_scraper.backtest.engine import BacktestEngine
from tradingview_scraper.settings import set_active_settings, TradingViewScraperSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run Production Pipeline")
    parser.add_argument("--profile", help="Settings profile", required=True)
    parser.add_argument("--manifest", help="Manifest path", default="configs/manifest.json")
    parser.add_argument("--run-id", help="Explicit run ID")
    args = parser.parse_args()

    # Bootstrap settings
    settings = TradingViewScraperSettings(profile=args.profile, manifest_path=Path(args.manifest), run_id=args.run_id)
    set_active_settings(settings)

    logger.info(f"Starting Production Pipeline | Profile: {settings.profile} | RunID: {settings.run_id}")

    # Initialize Engine
    engine = BacktestEngine()
    engine.load_data()

    # Run Tournament
    engine.run_tournament()


if __name__ == "__main__":
    main()
