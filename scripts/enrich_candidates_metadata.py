import argparse
import json
import logging
import os
from typing import Any, Dict

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("metadata_enrichment")


def get_asset_class(symbol: str) -> str:
    """Heuristic to determine asset class from symbol."""
    if ":" not in symbol:
        return "UNKNOWN"
    exchange = symbol.split(":")[0].upper()
    if exchange in ["BINANCE", "OKX", "BYBIT", "BITGET"]:
        return "CRYPTO"
    if exchange in ["NYSE", "NASDAQ", "AMEX"]:
        return "EQUITY"
    if exchange in ["OANDA", "THINKMARKETS", "FOREXCOM"]:
        return "FOREX"
    if exchange in ["CME", "CBOT", "NYMEX", "COMEX"]:
        return "FUTURES"
    return "CFD"


def get_defaults(asset_class: str, symbol: str) -> Dict[str, Any]:
    """Returns institutional defaults based on asset class."""
    if asset_class == "CRYPTO":
        is_perp = symbol.endswith(".P")
        return {
            "tick_size": 0.00000001 if not is_perp else 0.01,
            "lot_size": 0.001,
            "price_precision": 8 if not is_perp else 2,
            "min_qty": 0.001,
            "value_traded": 1e8,
        }
    if asset_class == "FOREX":
        is_jpy = "JPY" in symbol
        return {
            "tick_size": 0.001 if is_jpy else 0.00001,
            "lot_size": 1000.0,
            "price_precision": 3 if is_jpy else 5,
            "min_qty": 1000.0,
            "value_traded": 1e9,
        }
    if asset_class == "EQUITY":
        return {
            "tick_size": 0.01,
            "lot_size": 1.0,
            "price_precision": 2,
            "min_qty": 1.0,
            "value_traded": 5e8,
        }
    # Default for FUTURES/CFD
    return {
        "tick_size": 0.01,
        "lot_size": 1.0,
        "price_precision": 2,
        "min_qty": 1.0,
        "value_traded": 1e8,
    }


def enrich_metadata(candidates_path: str = "data/lakehouse/portfolio_candidates_raw.json", returns_path: str = "data/lakehouse/portfolio_returns.pkl"):
    if not os.path.exists(candidates_path):
        logger.error(f"Candidates file not found: {candidates_path}")
        return

    with open(candidates_path, "r") as f:
        candidates = json.load(f)

    candidate_map = {c["symbol"]: c for c in candidates}

    # 1. Synchronize with Returns Universe
    if os.path.exists(returns_path):
        returns = pd.read_pickle(returns_path)
        active_symbols = returns.columns.tolist()

        added_count = 0
        for symbol in active_symbols:
            if symbol not in candidate_map:
                asset_class = get_asset_class(symbol)
                new_cand = {
                    "symbol": symbol,
                    "identity": symbol.split(":")[-1] if ":" in symbol else symbol,
                    "direction": "LONG",
                    "value_traded": 1e9,
                    "sector": "Crypto" if asset_class == "CRYPTO" else "Financial",
                    "asset_class": asset_class,
                }
                candidates.append(new_cand)
                candidate_map[symbol] = new_cand
                added_count += 1
        if added_count > 0:
            logger.info(f"➕ Added {added_count} missing symbols from returns matrix.")

    # 2. Apply Institutional Defaults
    enriched_count = 0
    for c in candidates:
        symbol = c.get("symbol", "UNKNOWN")
        asset_class = c.get("asset_class") or get_asset_class(symbol)
        c["asset_class"] = asset_class

        defaults = get_defaults(asset_class, symbol)
        is_enriched = False

        for key, val in defaults.items():
            current_val = c.get(key)
            # Treat 0.0 or None or NaN as "missing" for liquidity fields
            if key == "value_traded":
                if current_val is None or (isinstance(current_val, float) and (np.isnan(current_val) or current_val <= 0.0)):
                    c[key] = val
                    is_enriched = True
            elif current_val is None or (isinstance(current_val, float) and np.isnan(current_val)):
                c[key] = val
                is_enriched = True

        # 3. Pre-Selection ECI Estimator (Step 5.5 Audit)
        # Prevents high-cost assets from consuming rate limits in Step 7
        adv = float(c.get("value_traded") or c.get("Value.Traded") or 1e-9)
        # Use a conservative 0.5 (50% vol) for early estimation if real vol is missing
        vol_est = float(c.get("Volatility.D") or 0.5) / 100.0 if "Volatility.D" in c else 0.5
        eci_est = vol_est * np.sqrt(1e6 / adv)

        # Capture Alpha Proxy from scanner (Perf.3M annualized)
        p3m = float(c.get("Perf.3M") or 0.0)
        annual_alpha_est = (1 + p3m / 100.0) ** 4 - 1

        c["eci_estimate"] = float(eci_est)
        c["eci_pre_veto"] = bool((annual_alpha_est - eci_est) < 0.005)

        if is_enriched:
            enriched_count += 1

    # 3. Save Enriched Pool
    with open(candidates_path, "w") as f:
        json.dump(candidates, f, indent=2)

    logger.info(f"✅ Total candidates: {len(candidates)}. Enriched {enriched_count} with institutional defaults.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich candidate manifests with liquidity metadata.")
    parser.add_argument("--candidates", default="data/lakehouse/portfolio_candidates_raw.json", help="Path to the candidates JSON file to enrich")
    parser.add_argument("--returns", default="data/lakehouse/portfolio_returns.pkl", help="Optional returns matrix to align against")
    args = parser.parse_args()

    enrich_metadata(candidates_path=args.candidates, returns_path=args.returns)


if __name__ == "__main__":
    main()
