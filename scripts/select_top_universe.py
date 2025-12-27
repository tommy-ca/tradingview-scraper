import glob
import json
import logging
import os
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("select_top_universe")


def get_asset_identity(symbol: str) -> str:
    """
    Extracts canonical identity of an asset to group redundant venues.
    Examples:
      BINANCE:BTCUSDT.P -> BTC/USDT
      OKX:BTC-USDT-SWAP -> BTC/USDT
      COMEX:SI1! -> SI
      COMEX:SIH2026 -> SI
    """
    try:
        raw = symbol.split(":")[-1].upper()
        # 1. Handle Futures (strip contract dates)
        for prefix in ["GC", "SI", "HG", "PL", "PA", "ZC", "ZS", "ZW"]:
            if raw.startswith(prefix):
                return prefix

        # 2. Handle Crypto (base/quote)
        # Remove common suffixes
        clean = raw.replace(".P", "").replace(".F", "").replace("-SWAP", "").replace("-SPOT", "")
        # Handle dashes
        if "-" in clean:
            parts = clean.split("-")
            # Filter out known junk parts
            parts = [p for p in parts if p not in ["USDT", "USDC", "USD", "BUSD", "DAI", "EUR", "GBP"]]
            if len(parts) >= 1:
                return parts[0]

        # Heuristic for base/quote (e.g. BTCUSDT -> BTC/USDT)
        for quote in ["USDT", "USDC", "USD", "BUSD", "DAI", "EUR", "GBP"]:
            if clean.endswith(quote) and len(clean) > len(quote):
                base = clean[: -len(quote)]
                return base

        return clean
    except Exception:
        return symbol


def get_asset_class(category: str) -> str:
    """Maps granular categories to broad institutional asset classes."""
    c = category.upper()
    if any(x in c for x in ["BOND", "ETF"]) and "STOCKS" not in c:
        return "FIXED_INCOME"
    if any(x in c for x in ["BINANCE", "BYBIT", "OKX", "BITGET", "CRYPTO"]):
        return "CRYPTO"
    if any(x in c for x in ["NASDAQ", "NYSE", "AMEX", "US_STOCKS", "US_ETF"]):
        return "EQUITIES"
    if any(x in c for x in ["CME", "COMEX", "NYMEX", "CBOT", "FUTURES"]):
        return "FUTURES"
    if "FOREX" in c:
        return "FOREX"
    return "OTHER"


def select_top_universe(mode: str = "raw"):
    files = glob.glob("export/universe_selector_*.json")

    # 1. Load All Items
    all_items = []
    for f in files:
        parts = os.path.basename(f).split("_")
        try:
            clean = [p for p in parts if p not in ["universe", "selector"] and not p[0].isdigit()]
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

        try:
            with open(f, "r") as j:
                raw_data = json.load(j)
                items = []
                if isinstance(raw_data, dict):
                    items = raw_data.get("data", [])
                elif isinstance(raw_data, list):
                    items = raw_data

                file_direction = "SHORT" if "_short" in f.lower() else "LONG"
                for i in items:
                    if isinstance(i, dict) and "symbol" in i:
                        i["_direction"] = file_direction
                        i["_category"] = category
                        i["_asset_class"] = get_asset_class(category)
                        i["_identity"] = get_asset_identity(i["symbol"])
                        all_items.append(i)
        except Exception as e:
            logger.error(f"Error reading {f}: {e}")

    # 2. Deduplicate and Score
    unique_assets = {}
    for item in all_items:
        sym = item["symbol"]
        if sym not in unique_assets:
            unique_assets[sym] = item

    scored_items = list(unique_assets.values())
    for item in scored_items:
        v_traded = float(item.get("Value.Traded", 0) or 0)
        adx = float(item.get("ADX", 0) or 0)
        vol = float(item.get("Volatility.D", 0) or 0)
        perf3m = float(item.get("Perf.3M", 0) or 0)
        perf6m = float(item.get("Perf.6M", 0) or 0)
        is_long = item.get("_direction", "LONG") == "LONG"

        # Direction-aware performance score
        # For LONG: positive is good. For SHORT: negative is good.
        p3 = perf3m if is_long else -perf3m
        p6 = perf6m if is_long else -perf6m
        p_avg = (p3 + p6) / 2

        # Updated Alpha Score: Liquidity, Trend, Vol, Perf
        score = 0.3 * min(1.0, v_traded / 1e9) + 0.3 * min(1.0, adx / 50) + 0.1 * min(1.0, vol / 10) + 0.3 * min(1.0, p_avg / 50)
        item["_alpha_score"] = score

    # 3. Canonical Merging (Best Venue per Identity)
    identity_groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in scored_items:
        ident = item["_identity"]
        if ident not in identity_groups:
            identity_groups[ident] = []
        identity_groups[ident].append(item)

    merged_pool = []
    for _, group in identity_groups.items():
        group.sort(key=lambda x: x["_alpha_score"], reverse=True)
        primary = group[0]
        if len(group) > 1:
            primary["alternative_venues"] = [x["symbol"] for x in group[1:]]
        merged_pool.append(primary)

    # 4. Filter by Asset Class
    final_candidates = []
    asset_classes = ["CRYPTO", "EQUITIES", "FUTURES", "FOREX", "FIXED_INCOME", "OTHER"]

    class_limit = int(os.getenv("UNIVERSE_CLASS_LIMIT", "30"))

    for ac in asset_classes:
        class_items = [x for x in merged_pool if x["_asset_class"] == ac]
        class_items.sort(key=lambda x: x["_alpha_score"], reverse=True)
        top_class = class_items[:class_limit]
        logger.info(f"Asset Class: {ac} - Selected {len(top_class)} symbols")
        final_candidates.extend(top_class)

    # 5. Global Truncation if in 'top' mode
    if mode == "top":
        final_candidates.sort(key=lambda x: x["_alpha_score"], reverse=True)
        final_candidates = final_candidates[: int(os.getenv("UNIVERSE_TOTAL_LIMIT", "80"))]

    # Map to final format
    output_universe = []
    for item in final_candidates:
        output_universe.append(
            {
                "symbol": item["symbol"],
                "description": item.get("description", item.get("name", "N/A")),
                "sector": item.get("sector", "N/A"),
                "market": item["_category"],
                "asset_class": item["_asset_class"],
                "identity": item["_identity"],
                "close": item.get("close", 0),
                "value_traded": item.get("Value.Traded", 0),
                "adx": item.get("ADX", 0),
                "atr": item.get("ATR", 0),
                "direction": item["_direction"],
                "alpha_score": item["_alpha_score"],
                "alternative_venues": item.get("alternative_venues", []),
            }
        )

    output_file = "data/lakehouse/portfolio_candidates.json"
    if mode == "raw":
        output_file = "data/lakehouse/portfolio_candidates_raw.json"

    with open(output_file, "w") as f_out:
        json.dump(output_universe, f_out, indent=2)

    logger.info(f"Saved {len(output_universe)} candidates to {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["raw", "top"], default="raw")
    args = parser.parse_args()
    select_top_universe(mode=args.mode)
