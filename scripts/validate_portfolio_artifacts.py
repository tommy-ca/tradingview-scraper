import argparse
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd

from tradingview_scraper.symbols.stream.lakehouse import LakehouseStorage
from tradingview_scraper.symbols.stream.metadata import DataProfile, MetadataCatalog, get_symbol_profile

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("validate_portfolio")

# Configuration
LAKEHOUSE_PATH = "data/lakehouse"
CANDIDATES_FILE = os.path.join(LAKEHOUSE_PATH, "portfolio_candidates.json")
RETURNS_FILE = os.path.join(LAKEHOUSE_PATH, "portfolio_returns.pkl")
FRESHNESS_THRESHOLD_HOURS = 72


class PortfolioValidator:
    def __init__(self):
        self.storage = LakehouseStorage(base_path=LAKEHOUSE_PATH)
        self.catalog = MetadataCatalog(base_path=LAKEHOUSE_PATH)
        self.results_by_profile: Dict[DataProfile, List[Dict[str, Any]]] = {p: [] for p in DataProfile}
        self.summary: Dict[str, Any] = {
            "total": 0,
            "profiles": {p.value: 0 for p in DataProfile},
            "status_counts": {"OK": 0, "OK (MARKET CLOSED)": 0, "DEGRADED (GAPS)": 0, "STALE": 0, "MISSING": 0, "DROPPED": 0},
        }

    def run_validation(self, type_filter: str = "all"):
        print("\n" + "=" * 100)
        print(f"PORTFOLIO ARTIFACT DASHBOARD - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        if type_filter != "all":
            print(f"Filter: {type_filter}")
        print("=" * 100)

        # 1. Load Candidates
        if not os.path.exists(CANDIDATES_FILE):
            logger.error(f"❌ Candidates file missing: {CANDIDATES_FILE}")
            return

        with open(CANDIDATES_FILE, "r") as f:
            candidates = json.load(f)

        # 2. Load Returns Matrix
        returns_symbols = set()
        if os.path.exists(RETURNS_FILE):
            try:
                returns_df = pd.read_pickle(RETURNS_FILE)
                returns_symbols = set(returns_df.columns)
            except Exception:
                pass

        now = datetime.now()
        lookback_days = int(os.getenv("PORTFOLIO_LOOKBACK_DAYS", "100"))
        lookback_cutoff = (now - timedelta(days=lookback_days)).timestamp()

        # 3. Audit each symbol
        for c in candidates:
            symbol = c["symbol"]
            meta = self.catalog.get_instrument(symbol)
            profile = get_symbol_profile(symbol, meta)

            # Apply filter
            if type_filter == "crypto" and profile != DataProfile.CRYPTO:
                continue
            if type_filter == "trad" and profile == DataProfile.CRYPTO:
                continue

            self.summary["total"] = self.summary["total"] + 1
            self.summary["profiles"][profile.value] = self.summary["profiles"][profile.value] + 1

            # Integrity checks
            file_path = self.storage._get_path(symbol, "1d")
            file_exists = os.path.exists(file_path)
            last_ts = self.storage.get_last_timestamp(symbol, "1d")

            # 1. Missing check
            if not file_exists:
                status = "MISSING"
                self._record(profile, symbol, status)
                continue

            # 2. Freshness check
            is_fresh = False
            if last_ts:
                last_dt = datetime.fromtimestamp(last_ts)
                is_fresh = (now - last_dt).total_seconds() / 3600 <= FRESHNESS_THRESHOLD_HOURS

            if not is_fresh:
                status = "STALE"
                self._record(profile, symbol, status, last_ts)
                continue

            # 3. Gap check
            all_gaps = self.storage.detect_gaps(symbol, "1d", profile=profile)
            # Filter gaps within lookback
            recent_gaps = [g for g in all_gaps if g[1] > lookback_cutoff]

            status = "OK"
            if recent_gaps:
                status = "DEGRADED (GAPS)"
            elif all_gaps:
                status = "OK (MARKET CLOSED)"
            else:
                status = "OK"

            # 4. Matrix check
            if symbol not in returns_symbols:
                status = "DROPPED"

            self._record(profile, symbol, status, last_ts, len(recent_gaps))

        self._print_dashboard()

    def _record(self, profile, symbol, status, last_ts=None, gap_count=0):
        last_date = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d") if last_ts else "N/A"
        self.results_by_profile[profile].append({"symbol": symbol, "status": status, "last_date": last_date, "gaps": gap_count})
        self.summary["status_counts"][status] += 1

    def _print_dashboard(self):
        # Display by profile
        for profile in DataProfile:
            results = self.results_by_profile[profile]
            if not results:
                continue

            print(f"\n[ {profile.value} ASSETS ]")
            print(f"{'SYMBOL':<25} | {'STATUS':<20} | {'LAST DATE':<12} | {'RECENT GAPS'}")
            print("-" * 80)

            # Sort by status (critical first) then symbol
            sorted_results = sorted(results, key=lambda x: (x["status"] != "OK", x["symbol"]))
            for r in sorted_results:
                icon = "✅" if "OK" in r["status"] else "❌" if r["status"] in ["MISSING", "STALE", "DEGRADED (GAPS)"] else "⚠️"
                print(f"{r['symbol']:<25} | {icon} {r['status']:<17} | {r['last_date']:<12} | {r['gaps']}")

        print("\n" + "=" * 100)
        print("SUMMARY BY STATUS")
        print("-" * 40)
        for status, count in self.summary["status_counts"].items():
            if count > 0:
                print(f"{status:<20}: {count}")
        print("=" * 100)

        status_counts: Dict[str, int] = self.summary["status_counts"]
        unready = status_counts["MISSING"] + status_counts["STALE"] + status_counts["DEGRADED (GAPS)"]

        if unready > 0:
            print("\nACTIONABLE ADVICE:")
            if status_counts["MISSING"] or status_counts["STALE"]:
                print("👉 Backfill missing/stale assets: make prep BACKFILL=1 GAPFILL=0")
            if status_counts["DEGRADED (GAPS)"]:
                print("👉 Repair unexpected gaps: uv run scripts/repair_portfolio_gaps.py --type all")
        else:
            print("\n✅ Targeted assets are HEALTHY or have normal market closures.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["crypto", "trad", "all"], default="all")
    args = parser.parse_args()

    validator = PortfolioValidator()
    validator.run_validation(type_filter=args.type)
