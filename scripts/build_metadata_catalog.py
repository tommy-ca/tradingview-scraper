import argparse
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any, List, Optional

import pandas as pd

from tradingview_scraper.symbols.stream.fetching import (
    _validate_symbol_record_for_upsert,
    fetch_tv_metadata,
)
from tradingview_scraper.symbols.stream.metadata import DEFAULT_EXCHANGE_METADATA, ExchangeCatalog, MetadataCatalog

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger("build_metadata_catalog")


def validate_path(path_str: str) -> Path:
    """Validates that a path exists and is within the project root."""
    try:
        path = Path(path_str).resolve()
        # Assuming the script runs from project root or we can find it
        # Ideally we find the project root dynamically, but CWD is usually project root in this setup
        root = Path.cwd().resolve()

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        if not path.is_relative_to(root):
            raise ValueError(f"Security Violation: Path {path} is outside project root")

        return path
    except Exception as e:
        logger.error(f"Path validation failed: {e}")
        raise e


def parse_candidates(data: Any) -> List[str]:
    """
    Parses a polymorphic JSON list of candidates.
    Supports: ["BTCUSDT", ...] or [{"symbol": "BTCUSDT"}, ...]
    """
    if not isinstance(data, list):
        raise ValueError("Root element must be a list")

    symbols = set()
    for item in data:
        if isinstance(item, str):
            symbols.add(item)
        elif isinstance(item, dict) and "symbol" in item:
            val = item["symbol"]
            if val:
                symbols.add(str(val))
        else:
            logger.debug(f"Skipping malformed item: {item}")

    return sorted(list(symbols))


class MetadataIngestionJob:
    def __init__(self, candidates_file: Optional[str] = None, symbols: Optional[List[str]] = None, from_catalog: bool = False, catalog_path: str = "data/lakehouse/symbols.parquet", workers: int = 3):
        self.catalog_path = Path(catalog_path)
        self.workers = workers
        self.target_symbols: List[str] = []

        self._resolve_targets(candidates_file, symbols, from_catalog)

    def _resolve_targets(self, candidates_file, symbols, from_catalog):
        if symbols:
            self.target_symbols = sorted(list(set(symbols)))
            logger.info(f"Loaded {len(self.target_symbols)} symbols from CLI args")

        elif candidates_file:
            path = validate_path(candidates_file)
            with open(path, "r") as f:
                data = json.load(f)
            self.target_symbols = parse_candidates(data)
            logger.info(f"Loaded {len(self.target_symbols)} symbols from {candidates_file}")

        elif from_catalog:
            if self.catalog_path.exists():
                try:
                    df = pd.read_parquet(self.catalog_path)
                    if "active" in df.columns:
                        df = df[df["active"] == True]
                    # Use explicit cast to Series
                    symbol_series = pd.Series(df["symbol"])
                    self.target_symbols = sorted(symbol_series.dropna().unique().tolist())
                    logger.info(f"Loaded {len(self.target_symbols)} symbols from catalog")
                except Exception as e:
                    logger.error(f"Failed to read catalog: {e}")
                    raise e
            else:
                logger.error(f"Catalog not found at {self.catalog_path}")

        if not self.target_symbols:
            logger.warning("No target symbols resolved.")

    def run(self):
        if not self.target_symbols:
            logger.error("Aborting: No symbols to process.")
            return

        # Backup existing catalog (belt and suspenders, atomic write handles safety mostly)
        if self.catalog_path.exists():
            backup_path = self.catalog_path.with_suffix(".parquet.bak")
            try:
                shutil.copy2(self.catalog_path, backup_path)
                logger.info(f"Backed up catalog to {backup_path}")
            except Exception as e:
                logger.warning(f"Failed to create backup: {e}")

        logger.info(f"Fetching metadata for {len(self.target_symbols)} symbols with {self.workers} workers...")
        catalog_data = fetch_tv_metadata(self.target_symbols, max_workers=self.workers)

        if catalog_data:
            # Initialize catalog pointing to the correct directory
            base_path = self.catalog_path.parent
            catalog = MetadataCatalog(base_path=base_path)

            validated_data = [r for r in catalog_data if _validate_symbol_record_for_upsert(r)]

            if validated_data:
                catalog.upsert_symbols(validated_data)
                logger.info(f"Upserted {len(validated_data)} symbols to catalog.")

            ex_catalog = ExchangeCatalog(base_path=base_path)
            exchanges = {r["exchange"] for r in catalog_data if r.get("exchange")}
            for ex in exchanges:
                defaults = DEFAULT_EXCHANGE_METADATA.get(ex, {})
                ex_catalog.upsert_exchange({"exchange": ex, "timezone": defaults.get("timezone", "UTC"), "is_crypto": defaults.get("is_crypto", False), "country": defaults.get("country", "Global")})
            logger.info("Catalog update complete.")
        else:
            logger.warning("No data fetched from TradingView.")


def main():
    parser = argparse.ArgumentParser(description="Build/Update Metadata Catalog")

    group = parser.add_mutually_exclusive_group()
    group.add_argument("--symbols", nargs="+", help="List of symbols to process")
    group.add_argument("--from-catalog", action="store_true", help="Refresh all active symbols from existing symbols.parquet")
    group.add_argument("--candidates-file", type=str, help="Refresh specific symbols from a JSON candidates file")

    parser.add_argument("--catalog-path", type=str, default="data/lakehouse/symbols.parquet")
    parser.add_argument("--workers", type=int, default=3, help="Number of concurrent workers (default: 3)")

    args = parser.parse_args()

    try:
        job = MetadataIngestionJob(candidates_file=args.candidates_file, symbols=args.symbols, from_catalog=args.from_catalog, catalog_path=args.catalog_path, workers=args.workers)
        job.run()
    except Exception as e:
        logger.error(f"Job failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
