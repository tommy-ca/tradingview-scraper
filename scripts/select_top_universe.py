import glob
import json
import logging
import os
from typing import Any, Dict, List

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("select_top_universe")


def get_canonical_name(symbol: str) -> str:
    """Extracts base pair name from exchange:pair string."""
    try:
        pair = symbol.split(":")[-1]
        # Remove .P for perps and .F for futures if present
        canonical = pair.replace(".P", "").replace(".F", "").upper()
        return canonical
    except Exception:
        return symbol


def select_top_universe(mode: str = "raw"):
    files = glob.glob("export/universe_selector_*.json")

    categories: Dict[str, List[Dict[str, Any]]] = {}

    for f in files:
        # Determine category from filename
        parts = os.path.basename(f).split("_")
        try:
            # remove universe, selector, date
            clean = [p for p in parts if p not in ["universe", "selector"] and not p[0].isdigit()]

            # Simple heuristic: Exchange + Type
            exchange = "UNKNOWN"
            mtype = "UNKNOWN"

            for p in clean:
                if p.upper() in ["BINANCE", "BYBIT", "OKX", "BITGET", "NASDAQ", "NYSE", "AMEX", "CME", "FOREX", "US", "BOND", "OANDA", "THINKMARKETS"]:
                    exchange = p.upper()
                if p.upper() in ["SPOT", "PERP", "FUTURES", "STOCKS", "ETF", "BONDS", "CFD"]:
                    mtype = p.upper()

            category = f"{exchange}_{mtype}"

        except Exception:
            category = "UNKNOWN"

        if category not in categories:
            categories[category] = []

        try:
            with open(f, "r") as j:
                raw_data = json.load(j)

                items = []
                if isinstance(raw_data, dict):
                    items = raw_data.get("data", [])
                elif isinstance(raw_data, list):
                    items = raw_data

                if not items:
                    items = []

                # Enrich with direction and scan file name for tracking
                file_direction = "SHORT" if "_short" in os.path.basename(f).lower() else "LONG"
                for i in items:
                    if isinstance(i, dict):
                        i["_direction"] = file_direction
                        i["_category"] = category

                categories[category].extend(items)
        except Exception as e:
            logger.error(f"Error reading {f}: {e}")

    # Step 1: Alpha Ranking within each category
    for cat in list(categories.keys()):
        items = categories[cat]
        # Deduplicate by symbol within category
        unique_items = {}
        for item in items:
            if isinstance(item, dict) and "symbol" in item:
                unique_items[item["symbol"]] = item
        items = list(unique_items.values())

        if items:
            v_traded = np.array([float(x.get("Value.Traded", 0) or 0) for x in items])
            adx = np.array([float(x.get("ADX", 0) or 0) for x in items])
            vol = np.array([float(x.get("Volatility.D", 0) or 0) for x in items])
            # Performance metrics for proxies (Equities/Bonds)
            perf3m = np.array([float(x.get("Perf.3M", 0) or 0) for x in items])
            perf6m = np.array([float(x.get("Perf.6M", 0) or 0) for x in items])

            def norm(a):
                return (a - a.min()) / (a.max() - a.min() + 1e-9) if len(a) > 1 else np.array([1.0] * len(a))

            # Updated Discovery Alpha Score:
            # Liquidity (30%), Trend (30%), Volatility (10%), Performance (30%)
            alpha_scores = 0.3 * norm(v_traded) + 0.3 * norm(adx) + 0.1 * norm(vol) + 0.15 * norm(perf3m) + 0.15 * norm(perf6m)

            for i, item in enumerate(items):
                item["_alpha_score"] = float(alpha_scores[i])

            items.sort(key=lambda x: x.get("_alpha_score", 0), reverse=True)
            categories[cat] = items

    # Step 2: Global Canonical Merging for Crypto
    canonical_groups: Dict[str, List[Dict[str, Any]]] = {}
    other_assets: List[Dict[str, Any]] = []

    for cat, items in categories.items():
        is_crypto = any(x in cat for x in ["BINANCE", "BYBIT", "OKX", "BITGET", "CRYPTO"])
        for item in items:
            if is_crypto:
                canonical = get_canonical_name(item["symbol"])
                if canonical not in canonical_groups:
                    canonical_groups[canonical] = []
                canonical_groups[canonical].append(item)
            else:
                other_assets.append(item)

    merged_crypto = []
    for canonical, group in canonical_groups.items():
        # Sort by alpha score to find the best venue
        group.sort(key=lambda x: x.get("_alpha_score", 0), reverse=True)
        primary = group[0]
        if len(group) > 1:
            primary["alternative_venues"] = [x["symbol"] for x in group[1:]]
            # Store alpha scores of alternatives for future statsarb
            primary["alternative_alpha_scores"] = {x["symbol"]: x.get("_alpha_score", 0) for x in group[1:]}
        merged_crypto.append(primary)

    # Step 3: Final Selection based on mode
    all_final_candidates = merged_crypto + other_assets

    if mode == "top":
        all_final_candidates.sort(key=lambda x: x.get("_alpha_score", 0), reverse=True)
        limit = int(os.getenv("UNIVERSE_TOP_N", "60"))
        all_final_candidates = all_final_candidates[:limit]
    elif mode == "raw":
        # Still apply a loose global limit to prevent total bloat
        raw_limit = int(os.getenv("RAW_TOP_N", "150"))
        all_final_candidates.sort(key=lambda x: x.get("_alpha_score", 0), reverse=True)
        if len(all_final_candidates) > raw_limit:
            all_final_candidates = all_final_candidates[:raw_limit]

    final_universe = []
    for item in all_final_candidates:
        final_universe.append(
            {
                "symbol": item["symbol"],
                "description": item.get("description", "N/A"),
                "sector": item.get("sector", "N/A"),
                "market": item.get("_category", "UNKNOWN"),
                "close": item.get("close", 0),
                "value_traded": item.get("Value.Traded", 0),
                "adx": item.get("ADX", 0),
                "atr": item.get("ATR", 0),
                "direction": item.get("_direction", "LONG"),
                "alternative_venues": item.get("alternative_venues", []),
                "alternative_alpha_scores": item.get("alternative_alpha_scores", {}),
            }
        )

    output_file = "data/lakehouse/portfolio_candidates.json"
    if mode == "raw":
        output_file = "data/lakehouse/portfolio_candidates_raw.json"

    with open(output_file, "w") as f_out:
        json.dump(final_universe, f_out, indent=2)

    logger.info(f"Saved {len(final_universe)} candidates to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["raw", "top"], default="raw")
    args = parser.parse_args()
    select_top_universe(mode=args.mode)
