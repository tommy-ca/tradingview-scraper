import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, cast

import pandas as pd

from tradingview_scraper.pipelines.selection.base import (
    AdvancedToxicityValidator,
    FoundationHealthRegistry,
)
from tradingview_scraper.settings import get_settings
from tradingview_scraper.symbols.stream.fetching import (
    _validate_symbol_record_for_upsert,
    fetch_tv_metadata,
)
from tradingview_scraper.symbols.stream.metadata import MetadataCatalog

# Assume PersistentDataLoader is available via PYTHONPATH or install
try:
    from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader
except ImportError:
    # For testing environment where package might not be installed
    PersistentDataLoader = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingestion_service")


class IngestionService:
    def __init__(self, lakehouse_dir: Path | None = None, freshness_hours: int = 12):
        settings = get_settings()
        self.lakehouse_dir = lakehouse_dir or settings.lakehouse_dir
        self.freshness_hours = freshness_hours
        self.loader = PersistentDataLoader(lakehouse_path=str(self.lakehouse_dir)) if PersistentDataLoader else None

        # Ensure lakehouse exists
        self.lakehouse_dir.mkdir(parents=True, exist_ok=True)
        self.registry = FoundationHealthRegistry(path=self.lakehouse_dir / "foundation_health.json")
        self.metadata_catalog = MetadataCatalog(base_path=self.lakehouse_dir)

    def is_fresh(self, symbol: str) -> bool:
        """Check if symbol data exists and is fresh."""
        safe_sym = symbol.replace(":", "_")
        p_path = self.lakehouse_dir / f"{safe_sym}_1d.parquet"

        if not p_path.exists():
            return False

        mtime = p_path.stat().st_mtime
        age_hours = (time.time() - mtime) / 3600

        if age_hours < self.freshness_hours:
            logger.debug(f"{symbol} is fresh ({age_hours:.1f}h < {self.freshness_hours}h). Skipping.")
            return True

        logger.info(f"{symbol} is stale ({age_hours:.1f}h). Queueing for fetch.")
        return False

    def _ensure_metadata(self, candidates: List[Dict], workers: int):
        """Ensures that all candidates have entries in the metadata catalog."""
        symbols = [c["symbol"] for c in candidates]
        if not symbols:
            return

        missing_symbols = []
        for sym in symbols:
            # Check if symbol exists in catalog
            if not self.metadata_catalog.get_instrument(sym):
                missing_symbols.append(sym)

        if missing_symbols:
            logger.info(f"Hydrating metadata for {len(missing_symbols)} new symbols...")
            new_meta = fetch_tv_metadata(missing_symbols, max_workers=workers)

            validated_data = [r for r in new_meta if _validate_symbol_record_for_upsert(r)]
            if validated_data:
                self.metadata_catalog.upsert_symbols(validated_data)
                logger.info(f"Upserted {len(validated_data)} new symbols to metadata catalog.")

    def ingest(self, candidates: List[Dict[str, Any]], lookback_days: int = 500, workers: int = 10):
        """
        Main ingestion logic:
        1. Filter candidates for freshness (Idempotency).
        2. Ensure metadata exists for all candidates.
        3. Fetch missing/stale data.
        4. Validate toxicity.
        5. Commit to Lakehouse (PersistentLoader does this, but we validate before).
        """
        if not self.loader:
            raise RuntimeError("PersistentDataLoader not initialized.")

        # 1. Filter
        # Validate that 'c' is a dictionary and has 'symbol'
        validated_candidates = []
        for c in candidates:
            if isinstance(c, dict) and "symbol" in c:
                validated_candidates.append(c)
            else:
                logger.warning(f"Skipping invalid candidate format: {c}")

        # 2. Metadata Hydration (Integrated from build_metadata_catalog)
        self._ensure_metadata(validated_candidates, workers)

        to_fetch = [c for c in validated_candidates if not self.is_fresh(c["symbol"])]

        if not to_fetch:
            logger.info("All candidates are fresh. No ingestion needed.")
            return

        logger.info(f"Ingesting {len(to_fetch)} symbols with {workers} workers...")

        def _ingest_single(item: Dict[str, Any]):
            symbol = item["symbol"]
            try:
                # Fetch
                depth = lookback_days + 100
                if self.loader is None:
                    raise RuntimeError("Loader lost.")
                added = self.loader.sync(symbol, interval="1d", depth=depth, total_timeout=300)
                time.sleep(0.5)  # Throttling to avoid 429

                # Verify Added Records
                if added == 0:
                    logger.warning(f"Sync returned 0 new records for {symbol}. Marking as stale.")
                    self.registry.update_status(symbol, status="stale", reason="zero_records_added")
                    self.registry.save()
                    return

                # Verify Toxic
                safe_sym = symbol.replace(":", "_")
                p_path = self.lakehouse_dir / f"{safe_sym}_1d.parquet"

                if p_path.exists():
                    df = pd.read_parquet(p_path)

                    vol = cast(pd.Series, df["volume"]) if "volume" in df.columns else pd.Series()
                    close = cast(pd.Series, df["close"]) if "close" in df.columns else pd.Series()

                    is_toxic_ret = self.is_toxic(df)
                    is_toxic_vol = AdvancedToxicityValidator.is_volume_toxic(vol) if not vol.empty else False
                    is_stalled = AdvancedToxicityValidator.is_price_stalled(close) if not close.empty else False

                    if is_toxic_ret or is_toxic_vol or is_stalled:
                        reason = "return_spike" if is_toxic_ret else ("volume_spike" if is_toxic_vol else "price_stall")
                        logger.warning(f"TOXIC DATA DETECTED for {symbol} (Reason: {reason}). Deleting corrupted file.")
                        os.remove(p_path)
                        self.registry.update_status(symbol, status="toxic", reason=reason)
                    else:
                        logger.info(f"Successfully ingested {symbol}")
                        self.registry.update_status(symbol, status="healthy")

                    self.registry.save()

            except Exception as e:
                logger.error(f"Failed to ingest {symbol}: {e}")

        with ThreadPoolExecutor(max_workers=workers) as executor:
            executor.map(_ingest_single, to_fetch)

    def is_toxic(self, df: pd.DataFrame) -> bool:
        """Check for >500% daily returns."""
        if "close" not in df.columns:
            return False

        # Calculate returns
        # Sort by timestamp just in case
        if "timestamp" in df.columns:
            df = df.sort_values("timestamp")

        pct = df["close"].pct_change().dropna()
        if pct.empty:
            return False

        if pct.max() > 5.0:  # 500%
            return True
        if pct.min() < -0.99:  # -99% drop (suspicious for some assets, but maybe real. Keep focus on upside spikes)
            # Actually -99% happens in crypto rugs. The spike is the main "contamination" issue.
            pass

        return False

    def process_candidate_file(self, file_path: Path, workers: int = 10):
        """Load symbols from JSON and ingest."""
        if not file_path.exists():
            logger.error(f"Candidate file not found: {file_path}")
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        # Handle {meta, data} envelope or raw list
        candidates = []
        if isinstance(data, dict):
            if "data" in data and isinstance(data["data"], list):
                candidates = data["data"]
            else:
                logger.error(f"Invalid JSON envelope in {file_path}. Expected 'data' list.")
                return
        elif isinstance(data, list):
            candidates = data
        else:
            logger.error(f"Unknown JSON format in {file_path}")
            return

        self.ingest(candidates, workers=workers)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", help="Path to candidates.json", required=True)
    parser.add_argument("--lakehouse", help="Path to lakehouse dir", default=None)
    parser.add_argument("--workers", type=int, default=3, help="Concurrency level")
    args = parser.parse_args()

    lakehouse_arg = Path(args.lakehouse) if args.lakehouse else None
    service = IngestionService(lakehouse_dir=lakehouse_arg)
    service.process_candidate_file(Path(args.candidates), workers=args.workers)
