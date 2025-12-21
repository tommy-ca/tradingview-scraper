import argparse
import logging
import os
from typing import List

from tradingview_scraper.symbols.overview import Overview

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("build_metadata_catalog")


def fetch_tv_metadata(symbols: List[str]) -> List[dict]:
    """
    Fetches structural metadata from TradingView for a list of symbols.
    """
    from tradingview_scraper.symbols.stream.metadata import DEFAULT_EXCHANGE_METADATA

    ov = Overview()
    results = []

    # Fields we care about for the catalog
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

                pricescale = data.get("pricescale", 1)
                minmov = data.get("minmov", 1)
                tick_size = minmov / pricescale if pricescale else None

                exchange = data.get("exchange")
                ex_defaults = DEFAULT_EXCHANGE_METADATA.get(exchange, {})

                # Timezone Resolution: API > Exchange Default > UTC
                timezone = data.get("timezone") or ex_defaults.get("timezone", "UTC")

                # Session Resolution: API > Crypto Default > Unknown
                session = data.get("session")
                if not session:
                    session = "24x7" if data.get("type") in ["spot", "swap"] else "Unknown"

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

    return results


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
        catalog.upsert_symbols(catalog_data)

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
