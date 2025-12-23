import argparse
import logging
import os
from typing import List, Optional

from tradingview_scraper.symbols.overview import Overview

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_metadata_catalog")


def fetch_tv_metadata(symbols: List[str]) -> List[dict]:
    """
    Fetches structural metadata from TradingView for a list of symbols.
    Enhanced with validation and type consistency.
    """
    from tradingview_scraper.symbols.stream.metadata import DEFAULT_EXCHANGE_METADATA

    ov = Overview()
    results = []

    # Fields we care about for catalog
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

    total = len(symbols)
    for i, symbol in enumerate(symbols):
        if i % 10 == 0:
            logger.info(f"Processing {i}/{total}: {symbol}...")

        try:
            res = ov.get_symbol_overview(symbol, fields=fields)
            if res["status"] == "success":
                data = res["data"]

                # Validate and normalize critical fields
                pricescale = _validate_numeric_field(data.get("pricescale"), "pricescale", 1)
                minmov = _validate_numeric_field(data.get("minmov"), "minmov", 1)
                tick_size = minmov / pricescale if pricescale and pricescale > 0 else None

                exchange = data.get("exchange")
                if not exchange:
                    logger.warning(f"Missing exchange for {symbol}, skipping")
                    continue

                ex_defaults = DEFAULT_EXCHANGE_METADATA.get(exchange, {})

                # Timezone Resolution: API > Exchange Default > UTC
                timezone = data.get("timezone") or ex_defaults.get("timezone", "UTC")

                # Session Resolution: API > Crypto Default > Unknown
                session = data.get("session")
                if not session:
                    session = "24x7" if data.get("type") in ["spot", "swap"] else "Unknown"

                # Validate required fields
                validation_errors = _validate_symbol_record(symbol, data, exchange, pricescale, minmov, tick_size)
                if validation_errors:
                    for error in validation_errors:
                        logger.warning(f"Validation error for {symbol}: {error}")
                    # Only skip if critical errors, otherwise log and continue
                    critical_errors = [e for e in validation_errors if "critical" in e.lower()]
                    if critical_errors:
                        continue

                record = {
                    "symbol": symbol,
                    "exchange": exchange,
                    "base": data.get("base_currency"),
                    "quote": data.get("currency"),
                    "type": data.get("type"),
                    "subtype": data.get("subtype"),
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
                results.append(record)
            else:
                logger.warning(f"Failed to fetch {symbol}: {res.get('error')}")

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")

    logger.info(f"Successfully processed {len(results)}/{len(symbols)} symbols")
    return results


def _validate_numeric_field(value, field_name: str, default: int) -> int:
    """
    Validates and normalizes numeric fields to ensure type consistency.
    """
    if value is None or value == "":
        return default

    try:
        # Convert to int for type consistency
        normalized = int(float(value))
        if normalized <= 0:
            logger.warning(f"Invalid {field_name} value: {value}, using default: {default}")
            return default
        return normalized
    except (ValueError, TypeError):
        logger.warning(f"Could not parse {field_name} value: {value}, using default: {default}")
        return default


def _validate_symbol_record_for_upsert(record: dict) -> bool:
    """
    Validates a symbol record before upserting to catalog.
    """
    required_fields = ["symbol", "type"]

    for field in required_fields:
        if not record.get(field):
            logger.warning(f"Missing required field '{field}' for symbol {record.get('symbol', 'UNKNOWN')}")
            return False

    # Validate numeric fields
    numeric_fields = ["pricescale", "minmov"]
    for field in numeric_fields:
        value = record.get(field)
        if value is not None and (not isinstance(value, (int, float)) or value <= 0):
            logger.warning(f"Invalid {field} value for symbol {record['symbol']}: {value}")
            return False

    return True


def _validate_symbol_record(symbol: str, data: dict, exchange: str, pricescale: int, minmov: int, tick_size: Optional[float]) -> List[str]:
    """
    Validates a symbol record and returns a list of validation errors.
    """
    errors = []

    # Critical validations
    if not exchange:
        errors.append("CRITICAL: Missing exchange")
    if not data.get("type"):
        errors.append("CRITICAL: Missing type")
    if pricescale is None or pricescale <= 0:
        errors.append("CRITICAL: Invalid pricescale")
    if minmov is None or minmov <= 0:
        errors.append("CRITICAL: Invalid minmov")

    # Warning validations
    if tick_size is None or tick_size <= 0:
        errors.append("WARNING: Invalid tick_size calculation")

    if not data.get("description"):
        errors.append("WARNING: Missing description")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Build/Update Metadata Catalog")
    parser.add_argument("--symbols", nargs="+", help="List of symbols to process")
    parser.add_argument("--config", type=str, help="Path to universe config yaml")
    parser.add_argument("--limit", type=int, help="Override symbol limit")
    parser.add_argument("--liquidity-floor", type=float, help="Override liquidity floor (Value.Traded)")
    parser.add_argument("--universe", type=str, default="binance_top50", help="Fallback preset universe")
    args = parser.parse_args()

    target_symbols = []

    # 1. Resolve Symbols
    if args.symbols:
        target_symbols = args.symbols

    elif args.config:
        try:
            from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector, load_config

            logger.info(f"Loading universe from {args.config}...")
            if not os.path.exists(args.config):
                logger.error(f"Config file not found: {args.config}")
                return

            cfg = load_config(args.config)
            # Use a slightly higher limit for catalog building to capture candidates
            if args.limit:
                cfg.limit = args.limit
                cfg.base_universe_limit = args.limit
            else:
                cfg.limit = 100

            if args.liquidity_floor is not None:
                cfg.volume.value_traded_min = args.liquidity_floor
                logger.info(f"Liquidity floor overridden to: {args.liquidity_floor}")

            selector = FuturesUniverseSelector(cfg)
            resp = selector.run()

            if resp.get("status") in ["success", "partial_success"]:
                data = resp.get("data", [])
                target_symbols = [r["symbol"] for r in data]
                logger.info(f"Resolved {len(target_symbols)} symbols from config.")

                if resp.get("status") == "partial_success":
                    logger.warning(f"Universe selection had errors: {resp.get('errors')}")
            else:
                err = resp.get("error") or resp.get("errors")
                logger.error(f"Universe selection failed: {err}")
                return
        except ImportError:
            logger.error("Could not import FuturesUniverseSelector. Ensure PYTHONPATH is set.")
            return

    elif args.universe == "binance_top50":
        # Fallback hardcoded
        target_symbols = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BINANCE:SOLUSDT", "BINANCE:BNBUSDT", "BINANCE:XRPUSDT", "BINANCE:ADAUSDT", "BINANCE:DOGEUSDT", "BINANCE:AVAXUSDT"]

    if not target_symbols:
        logger.error("No symbols provided or resolved.")
        return

    # 2. Fetch Metadata
    logger.info(f"Starting metadata build for {len(target_symbols)} symbols...")
    catalog_data = fetch_tv_metadata(target_symbols)

    # 3. Upsert to Catalog
    if catalog_data:
        from tradingview_scraper.symbols.stream.metadata import DEFAULT_EXCHANGE_METADATA, ExchangeCatalog, MetadataCatalog

        # Symbol Catalog
        catalog = MetadataCatalog()  # Defaults to data/lakehouse

        # Pre-validate data before upserting
        validated_data = []
        for record in catalog_data:
            if _validate_symbol_record_for_upsert(record):
                validated_data.append(record)
            else:
                logger.warning(f"Skipping invalid record: {record.get('symbol', 'UNKNOWN')}")

        if validated_data:
            catalog.upsert_symbols(validated_data)
        else:
            logger.warning("No valid data to upsert")

        # Exchange Catalog Bootstrap
        ex_catalog = ExchangeCatalog()
        exchanges = {r["exchange"] for r in catalog_data if r.get("exchange")}
        for ex in exchanges:
            logger.info(f"Bootstrapping exchange info for {ex}...")
            defaults = DEFAULT_EXCHANGE_METADATA.get(ex, {})
            ex_catalog.upsert_exchange(
                {
                    "exchange": ex,
                    "timezone": defaults.get("timezone", "UTC"),
                    "is_crypto": defaults.get("is_crypto", True),
                    "country": defaults.get("country", "Global"),
                    "description": defaults.get("description", f"{ex} Exchange"),
                }
            )

        logger.info(f"Catalog update complete. {len(catalog_data)} symbols and {len(exchanges)} exchanges processed.")
    else:
        logger.warning("No data collected.")


if __name__ == "__main__":
    main()
