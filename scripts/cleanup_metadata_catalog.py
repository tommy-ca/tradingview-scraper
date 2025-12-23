#!/usr/bin/env python3
"""
Script to clean up existing metadata catalog by fixing data types and removing duplicates.
"""

import logging

import pandas as pd

from tradingview_scraper.symbols.stream.metadata import DEFAULT_EXCHANGE_METADATA, MetadataCatalog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cleanup_catalog")


def cleanup_metadata_catalog():
    """
    Cleans up the existing metadata catalog by:
    1. Fixing data types for pricescale and minmov
    2. Removing duplicate records
    3. Updating tick_size calculations
    4. Adding missing exchange metadata
    """
    logger.info("Starting metadata catalog cleanup...")

    catalog = MetadataCatalog()
    df = catalog._df

    if df.empty:
        logger.info("Catalog is empty, nothing to clean")
        return

    logger.info(f"Processing {len(df)} records...")

    # 1. Fix data types
    logger.info("Fixing data types...")

    # Convert pricescale and minmov to int
    df["pricescale"] = pd.to_numeric(df["pricescale"], errors="coerce").fillna(1).astype("Int64")
    df["minmov"] = pd.to_numeric(df["minmov"], errors="coerce").fillna(1).astype("Int64")

    # Recalculate tick_size
    logger.info("Recalculating tick_size...")
    df["tick_size"] = df.apply(lambda row: row["minmov"] / row["pricescale"] if pd.notna(row["minmov"]) and pd.notna(row["pricescale"]) and row["pricescale"] > 0 else None, axis=1)

    # 2. Fix timezone and session for crypto symbols
    logger.info("Fixing timezone and session for crypto symbols...")
    crypto_exchanges = {ex for ex, meta in DEFAULT_EXCHANGE_METADATA.items() if meta.get("is_crypto")}

    # Fix timezone for crypto symbols
    crypto_mask = df["exchange"].isin(crypto_exchanges)
    df.loc[crypto_mask & df["timezone"].isna(), "timezone"] = "UTC"

    # Fix session for crypto symbols
    crypto_types = ["spot", "swap"]
    crypto_session_mask = crypto_mask & df["type"].isin(crypto_types) & df["session"].isna()
    df.loc[crypto_session_mask, "session"] = "24x7"

    # 3. Remove duplicates, keeping only latest active record
    logger.info("Removing duplicates...")

    # Sort by symbol and updated_at to get latest record first
    df_sorted = df.sort_values(["symbol", "updated_at"], ascending=[True, False])

    # Keep first occurrence of each symbol (latest active record) and all historical records
    deduplicated = []
    seen_symbols = set()

    for idx, row in df_sorted.iterrows():
        sym = row["symbol"]

        # Always keep historical records
        if pd.notna(row.get("valid_until")):
            deduplicated.append(row)
        # Only keep latest active record for each symbol
        elif sym not in seen_symbols:
            deduplicated.append(row)
            seen_symbols.add(sym)

    # Create cleaned DataFrame
    cleaned_df = pd.DataFrame(deduplicated)

    # 4. Validate and fix exchange information
    logger.info("Validating exchange information...")

    # Add missing exchange metadata
    for exchange in cleaned_df["exchange"].dropna().unique():
        if exchange not in DEFAULT_EXCHANGE_METADATA:
            logger.warning(f"Exchange {exchange} not in default metadata, adding basic info")
            # This will be added to exchange catalog later

    # Replace the catalog DataFrame
    catalog._df = cleaned_df
    catalog.save()

    # Report results
    logger.info("Cleanup complete!")
    logger.info(f"Original records: {len(df)}")
    logger.info(f"After cleanup: {len(cleaned_df)}")
    logger.info(f"Duplicates removed: {len(df) - len(cleaned_df)}")

    # Show sample of cleaned data
    logger.info("Sample cleaned records:")
    sample_symbols = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "BYBIT:SOLUSDT"]
    for symbol in sample_symbols:
        record = catalog.get_instrument(symbol)
        if record:
            logger.info(f"  {symbol}: pricescale={record['pricescale']} ({type(record['pricescale'])}), minmov={record['minmov']} ({type(record['minmov'])}), tick_size={record['tick_size']}")


if __name__ == "__main__":
    cleanup_metadata_catalog()
