from __future__ import annotations

import argparse
import logging
import sys

from tradingview_scraper.utils.meta_returns import validate_sleeve_health

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--engines", help="Comma-separated engine allowlist (default: custom)")
    parser.add_argument("--profiles", help="Comma-separated risk profile allowlist (default: all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    def _parse_csv(value: str | None) -> list[str] | None:
        if value is None:
            return None
        items = [v.strip() for v in value.split(",") if v.strip()]
        return items or None

    if not validate_sleeve_health(args.run_id, args.threshold, engines=_parse_csv(args.engines), profiles=_parse_csv(args.profiles)):
        sys.exit(1)
    sys.exit(0)
