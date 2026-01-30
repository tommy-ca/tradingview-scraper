import argparse
import logging

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.meta_optimization import optimize_meta

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("optimize_meta_portfolio")


if __name__ == "__main__":
    settings = get_settings()
    default_returns = str(settings.prepare_summaries_run_dir() / "data")
    default_output = str(settings.prepare_summaries_run_dir() / "data" / "meta_optimized.json")

    parser = argparse.ArgumentParser()
    parser.add_argument("--returns", default=default_returns)
    parser.add_argument("--output", default=default_output)
    parser.add_argument("--profile", help="Specific risk profile to optimize (e.g. hrp)")
    parser.add_argument("--meta-profile", help="Meta profile name (e.g. meta_super_benchmark)")
    args = parser.parse_args()

    optimize_meta(args.returns, args.output, args.profile, args.meta_profile)
