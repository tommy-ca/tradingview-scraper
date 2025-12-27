import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd

from tradingview_scraper.symbols.stream.lakehouse import LakehouseStorage
from tradingview_scraper.symbols.stream.metadata import DataProfile, MetadataCatalog, get_symbol_profile

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("portfolio_auditor")

# Configuration
LAKEHOUSE_PATH = "data/lakehouse"
CANDIDATES_FILE = os.path.join(LAKEHOUSE_PATH, "portfolio_candidates.json")
RETURNS_FILE = os.path.join(LAKEHOUSE_PATH, "portfolio_returns.pkl")
OPTIMIZED_FILE = os.path.join(LAKEHOUSE_PATH, "portfolio_optimized_v2.json")
FRESHNESS_THRESHOLD_HOURS = 72


class PortfolioAuditor:
    def __init__(self):
        self.storage = LakehouseStorage(base_path=LAKEHOUSE_PATH)
        self.catalog = MetadataCatalog(base_path=LAKEHOUSE_PATH)
        self.results_by_profile: Dict[DataProfile, List[Dict[str, Any]]] = {p: [] for p in DataProfile}
        self.summary: Dict[str, Any] = {
            "total": 0,
            "profiles": {p.value: 0 for p in DataProfile},
            "status_counts": {"OK": 0, "OK (MARKET CLOSED)": 0, "DEGRADED (GAPS)": 0, "STALE": 0, "MISSING": 0, "DROPPED": 0},
        }
        self.audit_failures = []

    def run_health_check(self, type_filter: str = "all"):
        print("\n" + "=" * 100)
        print(f"PORTFOLIO DATA HEALTH CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)

        if not os.path.exists(CANDIDATES_FILE):
            logger.error(f"❌ Candidates file missing: {CANDIDATES_FILE}")
            return False

        with open(CANDIDATES_FILE, "r") as f:
            candidates = json.load(f)

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

        for c in candidates:
            symbol = c["symbol"]
            meta = self.catalog.get_instrument(symbol)
            profile = get_symbol_profile(symbol, meta)

            if type_filter == "crypto" and profile != DataProfile.CRYPTO:
                continue
            if type_filter == "trad" and profile == DataProfile.CRYPTO:
                continue

            self.summary["total"] += 1
            self.summary["profiles"][profile.value] += 1

            file_path = self.storage._get_path(symbol, "1d")
            file_exists = os.path.exists(file_path)
            last_ts = self.storage.get_last_timestamp(symbol, "1d")

            if not file_exists:
                self._record(profile, symbol, "MISSING")
                continue

            is_fresh = False
            if last_ts:
                last_dt = datetime.fromtimestamp(last_ts)
                is_fresh = (now - last_dt).total_seconds() / 3600 <= FRESHNESS_THRESHOLD_HOURS

            if not is_fresh:
                self._record(profile, symbol, "STALE", last_ts)
                continue

            all_gaps = self.storage.detect_gaps(symbol, "1d", profile=profile, start_ts=lookback_cutoff)
            recent_gaps = all_gaps

            status = "OK"
            if recent_gaps:
                status = "DEGRADED (GAPS)"
            elif all_gaps:
                status = "OK (MARKET CLOSED)"

            if symbol not in returns_symbols:
                status = "DROPPED"

            self._record(profile, symbol, status, last_ts, len(recent_gaps))

        self._print_health_dashboard()

        status_counts = self.summary["status_counts"]
        critical_health = status_counts["MISSING"] + status_counts["STALE"]
        return critical_health == 0

    def run_logic_audit(self):
        print("\n" + "=" * 100)
        print("PORTFOLIO QUANTITATIVE LOGIC AUDIT")
        print("=" * 100)

        if not os.path.exists(OPTIMIZED_FILE):
            print("⚠️ No optimized portfolio file found to audit.")
            return True

        with open(OPTIMIZED_FILE, "r") as f:
            data = json.load(f)

        all_passed = True
        profiles = data.get("profiles", {})

        for name, p_data in profiles.items():
            print(f"\n[ AUDITING PROFILE: {name.upper()} ]")
            assets = p_data.get("assets", [])
            clusters = p_data.get("clusters", [])

            # 1. Weight Normalization (100% sum)
            total_w = sum(a["Weight"] for a in assets)
            if abs(total_w - 1.0) > 0.001:
                self._fail(f"Profile '{name}' weight sum is {total_w:.4f} (expected 1.0)")
                all_passed = False
            else:
                print(f"✅ Weight Normalization: {total_w:.2%}")

            # 2. Cluster Concentration Cap (25%)
            cluster_weights = {c["Cluster_ID"]: c["Gross_Weight"] for c in clusters}
            over_capped = [c_id for c_id, w in cluster_weights.items() if w > 0.251]
            if over_capped:
                self._fail(f"Profile '{name}' clusters exceed 25% cap: {over_capped}")
                all_passed = False
            else:
                max_c = max(cluster_weights.values()) if cluster_weights else 0
                print(f"✅ Cluster Concentration: Max bucket is {max_c:.2%}")

            # 3. Barbell Insulation & Uniqueness
            if name == "barbell":
                aggressors = [a for a in assets if "AGGRESSOR" in a.get("Type", "")]
                core = [a for a in assets if "CORE" in a.get("Type", "")]

                # Uniqueness
                agg_clusters = set(str(a["Cluster_ID"]) for a in aggressors)
                if len(agg_clusters) != len(aggressors):
                    self._fail(f"Barbell aggressors are not from unique clusters! ({len(agg_clusters)} vs {len(aggressors)})")
                    all_passed = False
                else:
                    print(f"✅ Aggressor Uniqueness: {len(agg_clusters)} unique buckets")

                # Insulation
                core_clusters = set(str(a["Cluster_ID"]) for a in core)
                overlap = agg_clusters.intersection(core_clusters)
                if overlap:
                    self._fail(f"Barbell insulation breach! Overlap in clusters: {overlap}")
                    all_passed = False
                else:
                    print("✅ Risk Insulation: Zero overlap between Core and Aggressors")

                # Sleeve weights
                agg_w = sum(a["Weight"] for a in aggressors)
                if abs(agg_w - 0.10) > 0.005:
                    self._fail(f"Barbell aggressor weight is {agg_w:.4f} (expected 0.10)")
                    all_passed = False
                else:
                    print("✅ Sleeve Balance: 10% Aggressors / 90% Core")

            # 4. Metadata Completeness
            missing_metadata = [a["Symbol"] for a in assets if a.get("Sector") == "N/A" or not a.get("Description")]
            if missing_metadata:
                # Warning only, doesn't fail the audit unless it's a huge portion
                print(f"⚠️ Metadata Warning: {len(missing_metadata)} assets have incomplete sector/description.")
            else:
                print("✅ Metadata Completeness: 100%")

        if not all_passed:
            print("\n❌ LOGIC AUDIT FAILED")
            for f in self.audit_failures:
                print(f"  - {f}")
        else:
            print("\n✅ ALL QUANTITATIVE LOGIC CHECKS PASSED")

        return all_passed

    def _record(self, profile, symbol, status, last_ts=None, gap_count=0):
        last_date = datetime.fromtimestamp(last_ts).strftime("%Y-%m-%d") if last_ts else "N/A"
        self.results_by_profile[profile].append({"symbol": symbol, "status": status, "last_date": last_date, "gaps": gap_count})
        self.summary["status_counts"][status] += 1

    def _fail(self, message):
        self.audit_failures.append(message)

    def _print_health_dashboard(self):
        for profile in DataProfile:
            results = self.results_by_profile[profile]
            if not results:
                continue
            print(f"\n[ {profile.value} ASSETS ]")
            print(f"{'SYMBOL':<25} | {'STATUS':<20} | {'LAST DATE':<12} | {'RECENT GAPS'}")
            print("-" * 80)
            sorted_results = sorted(results, key=lambda x: (x["status"] != "OK", x["symbol"]))
            for r in sorted_results:
                icon = "✅" if "OK" in r["status"] else "❌" if r["status"] in ["MISSING", "STALE"] else "⚠️"
                print(f"{r['symbol']:<25} | {icon} {r['status']:<17} | {r['last_date']:<12} | {r['gaps']}")

        print("\n" + "=" * 100)
        print("SUMMARY BY STATUS")
        print("-" * 40)
        for status, count in self.summary["status_counts"].items():
            if count > 0:
                print(f"{status:<20}: {count}")
        print("=" * 100)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--type", choices=["crypto", "trad", "all"], default="all")
    parser.add_argument("--only-health", action="store_true")
    parser.add_argument("--only-logic", action="store_true")
    args = parser.parse_args()

    auditor = PortfolioAuditor()

    health_ok = True
    logic_ok = True

    if not args.only_logic:
        health_ok = auditor.run_health_check(type_filter=args.type)

    if not args.only_health:
        logic_ok = auditor.run_logic_audit()

    if not health_ok or not logic_ok:
        sys.exit(1)
    else:
        sys.exit(0)
