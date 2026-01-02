import argparse
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

import pandas as pd

from tradingview_scraper.symbols.overview import Overview
from tradingview_scraper.symbols.stream.metadata import DEFAULT_EXCHANGE_METADATA, ExchangeCatalog, MetadataCatalog, get_symbol_profile

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("build_metadata_catalog")


def _validate_numeric_field(value, field_name: str, default: int) -> int:
    """Validates and normalizes numeric fields to ensure type consistency."""
    if value is None or value == "":
        return default
    try:
        normalized = int(float(value))
        if normalized <= 0:
            return default
        return normalized
    except (ValueError, TypeError):
        return default


def _validate_symbol_record(symbol: str, data: dict, exchange: str, pricescale: int, minmov: int, tick_size: Optional[float]) -> List[str]:
    """Validates a symbol record and returns a list of validation errors."""
    errors = []
    if not exchange:
        errors.append("CRITICAL: Missing exchange")
    if not data.get("type"):
        errors.append("CRITICAL: Missing type")
    if pricescale is None or pricescale <= 0:
        errors.append("CRITICAL: Invalid pricescale")
    if minmov is None or minmov <= 0:
        errors.append("CRITICAL: Invalid minmov")
    return errors


def _validate_symbol_record_for_upsert(record: dict) -> bool:
    """Validates a symbol record before upserting to catalog."""
    required_fields = ["symbol", "type"]
    for field in required_fields:
        if not record.get(field):
            return False
    return True


def fetch_tv_metadata_single(symbol: str) -> Optional[dict]:
    """Fetches structural metadata from TradingView for a single symbol."""
    ov = Overview()
    fields = [
        "pricescale",
        "minmov",
        "minmove2",
        "currency",
        "base_currency",
        "exchange",
        "type",
        "subtype",
        "description",
        "sector",
        "industry",
        "country",
        "root",
        "expiration",
        "contract_type",
        "timezone",
        "session",
    ]

    try:
        res = ov.get_symbol_overview(symbol, fields=fields)
        if res["status"] == "success":
            data = res["data"]
            pricescale = _validate_numeric_field(data.get("pricescale"), "pricescale", 1)
            minmov = _validate_numeric_field(data.get("minmov"), "minmov", 1)
            tick_size = minmov / pricescale if pricescale and pricescale > 0 else None
            exchange = data.get("exchange")
            if not exchange:
                return None

            ex_defaults = DEFAULT_EXCHANGE_METADATA.get(exchange, {})
            timezone = data.get("timezone") or ex_defaults.get("timezone", "UTC")
            session = data.get("session")
            if not session:
                session = "24x7" if data.get("type") in ["spot", "swap"] else "Unknown"

            profile = get_symbol_profile(symbol, {"type": data.get("type"), "is_crypto": ex_defaults.get("is_crypto")})

            return {
                "symbol": symbol,
                "exchange": exchange,
                "base": data.get("base_currency"),
                "quote": data.get("currency"),
                "type": data.get("type"),
                "subtype": data.get("subtype"),
                "profile": profile.value,
                "description": data.get("description"),
                "sector": data.get("sector"),
                "industry": data.get("industry"),
                "country": data.get("country") or ex_defaults.get("country"),
                "pricescale": pricescale,
                "minmov": minmov,
                "tick_size": tick_size,
                "active": True,
                "lot_size": None,
                "contract_size": None,
                "timezone": timezone,
                "session": session,
            }
    except Exception as e:
        logger.error(f"Error processing {symbol}: {e}")
    return None


def fetch_tv_metadata(symbols: List[str], max_workers: int = 10) -> List[dict]:
    """Fetches structural metadata from TradingView concurrently."""
    results = []
    total = len(symbols)
    logger.info(f"Fetching metadata for {total} symbols using {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for i, result in enumerate(executor.map(fetch_tv_metadata_single, symbols)):
            if (i + 1) % 5 == 0 or i + 1 == total:
                logger.info(f"Processing [{i + 1}/{total}]: {symbols[i]}")
            if result:
                results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description="Build/Update Metadata Catalog")
    parser.add_argument("--symbols", nargs="+", help="List of symbols to process")
    parser.add_argument("--from-catalog", action="store_true", help="Refresh all active symbols from existing symbols.parquet")
    parser.add_argument("--candidates-file", type=str, help="Refresh specific symbols from a JSON candidates file")
    parser.add_argument("--catalog-path", type=str, default="data/lakehouse/symbols.parquet")
    parser.add_argument("--workers", type=int, default=10)
    args = parser.parse_args()

    target_symbols = []
    if args.symbols:
        target_symbols = args.symbols
    elif args.candidates_file:
        if os.path.exists(args.candidates_file):
            with open(args.candidates_file, "r") as f:
                cands = json.load(f)
            target_symbols = sorted({c["symbol"] for c in cands if "symbol" in c})
            logger.info(f"Loaded {len(target_symbols)} symbols from {args.candidates_file}")
    elif args.from_catalog:
        if os.path.exists(args.catalog_path):
            df = pd.read_parquet(args.catalog_path)
            if "active" in df.columns:
                df = df[df["active"] == True]
            # Use explicit cast to Series to satisfy type checker
            symbol_series = pd.Series(df["symbol"])
            target_symbols = sorted(symbol_series.dropna().unique().tolist())
            logger.info(f"Loaded {len(target_symbols)} symbols from catalog")

    if not target_symbols:
        logger.error("No target symbols resolved.")
        return

    catalog_data = fetch_tv_metadata(target_symbols, max_workers=args.workers)

    if catalog_data:
        catalog = MetadataCatalog()
        validated_data = [r for r in catalog_data if _validate_symbol_record_for_upsert(r)]

        if validated_data:
            catalog.upsert_symbols(validated_data)
            logger.info(f"Upserted {len(validated_data)} symbols to catalog.")

        ex_catalog = ExchangeCatalog()
        exchanges = {r["exchange"] for r in catalog_data if r.get("exchange")}
        for ex in exchanges:
            defaults = DEFAULT_EXCHANGE_METADATA.get(ex, {})
            ex_catalog.upsert_exchange({"exchange": ex, "timezone": defaults.get("timezone", "UTC"), "is_crypto": defaults.get("is_crypto", False), "country": defaults.get("country", "Global")})
        logger.info("Catalog update complete.")


if __name__ == "__main__":
    main()
