import argparse
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import ray
from tqdm import tqdm

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.contracts import FeatureStoreSchema
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash
from tradingview_scraper.utils.technicals import TechnicalRatings

# Explicit import for SchemaError
try:
    from pandera.errors import SchemaError
except ImportError:
    # Fallback for different pandera versions if needed
    class SchemaError(Exception):  # type: ignore
        pass


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


@ray.remote
def process_symbol_features(symbol: str, lakehouse_dir: Path) -> Optional[Dict[str, pd.Series]]:
    """Ray worker task to compute features for a single symbol."""
    safe_sym = symbol.replace(":", "_")
    file_path = lakehouse_dir / f"{safe_sym}_1d.parquet"

    if not file_path.exists():
        return None

    try:
        df = pd.read_parquet(file_path)
        df.columns = [c.lower() for c in df.columns]

        # Ensure DatetimeIndex
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        elif "date" in df.columns:
            df = df.set_index("date")

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        if df.index.tz is not None:
            df.index = df.index.tz_convert(None)

        if "close" not in df.columns:
            return None

        df = df.sort_index()

        # Calculate Technicals using optimized logic
        ma = TechnicalRatings.calculate_recommend_ma_series(df)
        osc = TechnicalRatings.calculate_recommend_other_series(df)

        # Optimized: Vectorized mean
        rating = (ma + osc) / 2.0

        # NaN Sanitization
        ma = ma.ffill(limit=3)
        osc = osc.ffill(limit=3)
        rating = rating.ffill(limit=3)

        return {"recommend_ma": ma, "recommend_other": osc, "recommend_all": rating}

    except Exception as e:
        # We don't want to crash the whole Ray cluster for one failed symbol
        return None


def atomic_save_parquet(df: pd.DataFrame, path: Path) -> None:
    """Safely persists a DataFrame to Parquet using a temporary file and atomic move."""
    temp_path = path.with_suffix(f".{os.getpid()}.tmp")
    try:
        df.to_parquet(temp_path, index=True)
        # shutil.move is safer across different filesystems than Path.replace/os.rename
        shutil.move(str(temp_path), str(path))
    finally:
        if temp_path.exists():
            temp_path.unlink()


@StageRegistry.register(
    id="foundation.backfill",
    name="Feature Backfill",
    description="Generates a PIT features matrix from OHLCV data.",
    category="foundation",
)
def backfill_features_stage(candidates_path: Optional[str] = None, output_path: Optional[str] = None, lakehouse_dir: Optional[str] = None):
    cand_p = Path(candidates_path) if candidates_path else None
    out_p = Path(output_path) if output_path else None
    lh_p = Path(lakehouse_dir) if lakehouse_dir else None

    service = BackfillService(lakehouse_dir=lh_p)
    service.run(candidates_path=cand_p, output_path=out_p)
    return True


class BackfillService:
    def __init__(self, lakehouse_dir: Optional[Path] = None):
        settings = get_settings()
        self.lakehouse_dir = lakehouse_dir or settings.lakehouse_dir

    def _get_lakehouse_symbols(self) -> List[str]:
        """Returns all symbols currently present in the Lakehouse."""
        symbols = []
        for p in self.lakehouse_dir.glob("*_1d.parquet"):
            stem = p.stem.replace("_1d", "")
            if "_" in stem:
                parts = stem.split("_", 1)
                symbols.append(f"{parts[0]}:{parts[1]}")
        return sorted(symbols)

    def run(self, candidates_path: Optional[Path] = None, output_path: Optional[Path] = None):
        """Main execution flow with Ray parallelization."""
        settings = get_settings()
        out_p = output_path or (settings.lakehouse_dir / "features_matrix.parquet")

        # 1. Resolve Symbols
        lakehouse_symbols = self._get_lakehouse_symbols()

        if candidates_path and candidates_path.exists():
            with open(candidates_path, "r") as f:
                candidates = json.load(f)
            provided_symbols = list(set([c.get("physical_symbol") or c.get("symbol") for c in candidates]))
            symbols = provided_symbols
        else:
            logger.info("No candidates file provided. Scanning full Lakehouse for symbols.")
            symbols = lakehouse_symbols

        logger.info(f"Backfilling features for {len(symbols)} unique symbols via Ray...")

        # Initialize Ray if not already
        if not ray.is_initialized():
            ray.init(ignore_reinit_error=True)

        # 2. Parallel Processing
        futures = [process_symbol_features.remote(s, self.lakehouse_dir) for s in symbols]

        results = {}
        for symbol, future in zip(symbols, tqdm(futures, desc="Computing Features")):
            res = ray.get(future)
            if res:
                for feat_name, series in res.items():
                    results[(symbol, feat_name)] = series

        if not results:
            logger.error("No ratings generated.")
            return

        # 3. Consolidation
        logger.info("Consolidating features matrix...")
        features_df = pd.DataFrame(results)
        features_df.columns.names = ["symbol", "feature"]
        features_df = features_df.dropna(how="all")

        # 4. Bulk Validation (Optimized)
        logger.info("Validating features matrix...")
        try:
            unique_symbols = features_df.columns.get_level_values("symbol").unique()
            # Still looping over symbols for now as FeatureStoreSchema expects specific column names,
            # but we could optimize further with a Regex schema if column names were flat.
            for sym in unique_symbols:
                sym_df = features_df.xs(sym, axis=1, level="symbol")
                FeatureStoreSchema.validate(sym_df)
        except SchemaError as e:
            logger.error(f"Schema Validation Failed: {e}")
            raise

        # 5. Save Artifact (Atomic)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        atomic_save_parquet(features_df, out_p)

        logger.info(f"Saved feature matrix to {out_p}")
        logger.info(f"Shape: {features_df.shape} | Hash: {get_df_hash(features_df)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", help="Path to portfolio_candidates.json")
    parser.add_argument("--output", help="Path to output features_matrix.parquet")
    parser.add_argument("--lakehouse", help="Path to lakehouse dir (optional)")

    args = parser.parse_args()

    service = BackfillService(lakehouse_dir=Path(args.lakehouse) if args.lakehouse else None)
    service.run(candidates_path=Path(args.candidates) if args.candidates else None, output_path=Path(args.output) if args.output else None)
