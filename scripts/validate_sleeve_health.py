import argparse
import sys
from typing import List, Optional

from tradingview_scraper.utils.health import validate_sleeve_health


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    if value is None:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items or None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--threshold", type=float, default=0.75)
    parser.add_argument("--engines", help="Comma-separated engine allowlist (default: custom)")
    parser.add_argument("--profiles", help="Comma-separated risk profile allowlist (default: all)")
    args = parser.parse_args()

    if not validate_sleeve_health(args.run_id, args.threshold, engines=_parse_csv(args.engines), profiles=_parse_csv(args.profiles)):
        sys.exit(1)
    sys.exit(0)
