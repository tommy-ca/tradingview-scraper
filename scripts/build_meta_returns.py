from __future__ import annotations

import argparse
import logging

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.meta_returns import build_meta_returns

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("build_meta_returns")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, help="Meta portfolio profile name")

    settings = get_settings()
    default_out = str(settings.lakehouse_dir / "meta_returns.pkl")

    parser.add_argument("--output", default=default_out)
    parser.add_argument("--profiles", help="Comma-separated risk profiles to build")
    args = parser.parse_args()

    target_profs = args.profiles.split(",") if args.profiles else None
    build_meta_returns(args.profile, args.output, target_profs)
