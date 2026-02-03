from __future__ import annotations

import argparse
import logging

from tradingview_scraper.backtest.meta import build_meta_returns
from tradingview_scraper.settings import get_settings

logger = logging.getLogger("build_meta_returns")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")

    settings = get_settings()
    default_out = str(settings.lakehouse_dir / "meta_returns.parquet")

    parser.add_argument("--output", default=default_out)
    parser.add_argument("--profiles", help="Comma-separated risk profiles to build")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    target_profs = args.profiles.split(",") if args.profiles else None
    build_meta_returns(meta_profile=args.profile, output_path=args.output, profiles=target_profs)
