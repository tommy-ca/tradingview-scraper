import argparse
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from tradingview_scraper.symbols.overview import Overview

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ingest_features")


class FeatureIngestionService:
    def __init__(self, lakehouse_dir: Path = Path("data/lakehouse"), workers: int = 10):
        self.lakehouse_dir = lakehouse_dir
        self.features_dir = lakehouse_dir / "features" / "tv_technicals_1d"
        self.features_dir.mkdir(parents=True, exist_ok=True)
        self.workers = workers
        self.overview = Overview()

    def fetch_technicals_single(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch technicals for a single symbol."""
        try:
            # We fetch ALL fields to get the technicals defined in Overview.TECHNICAL_FIELDS
            # Overview class automatically requests them if fields=None or we can specify
            fields = Overview.TECHNICAL_FIELDS + Overview.VOLATILITY_FIELDS + Overview.PERFORMANCE_FIELDS
            res = self.overview.get_symbol_overview(symbol, fields=fields)

            if res["status"] == "success" and res.get("data"):
                data = res["data"]

                # Map to schema keys (lowercase)
                return {
                    "symbol": symbol,
                    "recommend_all": data.get("Recommend.All"),
                    "recommend_ma": data.get("Recommend.MA"),
                    "recommend_other": data.get("Recommend.Other"),
                    "rsi": data.get("RSI"),
                    "adx": data.get("ADX"),
                    "ao": data.get("AO"),
                    "cci20": data.get("CCI20"),
                    "stoch_k": data.get("Stoch.K"),
                    "stoch_d": data.get("Stoch.D"),
                    "macd_macd": data.get("MACD.macd"),
                    "macd_signal": data.get("MACD.signal"),
                    "volatility_d": data.get("Volatility.D"),
                    "perf_w": data.get("Perf.W"),
                    "perf_1m": data.get("Perf.1M"),
                    # Add timestamp here or in batch
                }
        except Exception as e:
            logger.warning(f"Failed to fetch technicals for {symbol}: {e}")
        return None

    def ingest_batch(self, symbols: List[str]):
        """Fetch and store technicals for a batch of symbols."""
        if not symbols:
            return

        logger.info(f"Fetching technicals for {len(symbols)} symbols...")
        results = []

        # Current UTC timestamp for the snapshot
        now_ts = int(time.time())
        # Partition Date
        partition_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            for i, result in enumerate(executor.map(self.fetch_technicals_single, symbols)):
                if result:
                    result["timestamp"] = now_ts
                    results.append(result)
                if (i + 1) % 50 == 0:
                    logger.info(f"Processed {i + 1}/{len(symbols)}")

        if not results:
            logger.warning("No technicals fetched.")
            return

        # Create DataFrame
        df = pd.DataFrame(results)

        # Define Partition Path
        part_dir = self.features_dir / f"date={partition_date}"
        part_dir.mkdir(parents=True, exist_ok=True)

        # Save Parquet
        # We append a timestamp/uuid to filename to avoid overwrites in case of multiple runs per day?
        # Or just overwrite "part-0.parquet" if we assume one batch per day?
        # Let's use a timestamped filename to allow multiple batches.
        filename = f"part-{now_ts}.parquet"
        out_path = part_dir / filename

        df.to_parquet(out_path, index=False)
        logger.info(f"Saved {len(df)} records to {out_path}")

    def process_candidate_file(self, file_path: Path):
        """Load symbols from a candidates JSON file."""
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        symbols = []
        # Handle list or dict envelope
        candidates = data.get("data", []) if isinstance(data, dict) else data

        if isinstance(candidates, list):
            for c in candidates:
                if isinstance(c, dict) and "symbol" in c:
                    symbols.append(c["symbol"])
                elif isinstance(c, str):
                    symbols.append(c)

        # Dedupe
        symbols = sorted(list(set(symbols)))
        self.ingest_batch(symbols)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="Path to candidates.json")
    parser.add_argument("--lakehouse", default="data/lakehouse", help="Lakehouse root directory")
    parser.add_argument("--workers", type=int, default=10, help="Concurrency level")
    args = parser.parse_args()

    service = FeatureIngestionService(lakehouse_dir=Path(args.lakehouse), workers=args.workers)
    service.process_candidate_file(Path(args.candidates))
