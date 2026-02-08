import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional, Tuple, cast

import pandas as pd
import ray
from tqdm import tqdm

from tradingview_scraper.orchestration.compute import RayComputeEngine
from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash
from tradingview_scraper.utils.security import SecurityUtils
from tradingview_scraper.utils.technicals import TechnicalRatings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


def _process_single_symbol(symbol: str, lakehouse_dir: Path, output_dir: Optional[Path] = None) -> Optional[Tuple[str, str]]:
    """Logic for calculating features for a single symbol."""
    try:
        file_path = SecurityUtils.get_safe_path(lakehouse_dir, symbol)
        if not file_path.exists():
            return None

        df = pd.read_parquet(file_path)
        df.columns = [c.lower() for c in df.columns]

        # Ensure DatetimeIndex
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        elif "date" in df.columns:
            df = df.set_index("date")

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        from tradingview_scraper.utils.data_utils import ensure_utc_index

        ensure_utc_index(df)

        if "close" not in df.columns:
            return None

        df = df.sort_index()

        # Calculate Technicals using shared logic (Phase 630/640)
        ma = TechnicalRatings.calculate_recommend_ma_series(df)
        osc = TechnicalRatings.calculate_recommend_other_series(df)
        rating = TechnicalRatings.calculate_recommend_all_series(df)

        # CR-Hardening: NaN Sanitization (Phase 630)
        # Apply ffill with limit to preserve gap information
        ma = ma.ffill(limit=3)
        osc = osc.ffill(limit=3)
        rating = rating.ffill(limit=3)

        if output_dir:
            # Create a small DataFrame for this symbol's features
            # Use MultiIndex columns to match the expected format
            feat_df = pd.DataFrame({"recommend_ma": ma, "recommend_other": osc, "recommend_all": rating})

            # Sanitize symbol for filename
            symbol_safe = symbol.replace(":", "_")
            out_file = output_dir / f"{symbol_safe}_features.parquet"
            feat_df.to_parquet(out_file)
            return symbol, str(out_file)

        # Legacy return (though we should avoid this now)
        return symbol, "success"

    except Exception as e:
        logger.error(f"Error processing {symbol}: {e}")
        return None


@ray.remote
def _process_single_symbol_task(symbol: str, lakehouse_dir: Path, output_dir: Path) -> Optional[Tuple[str, str]]:
    """Distributed task wrapper."""
    return _process_single_symbol(symbol, lakehouse_dir, output_dir)


@StageRegistry.register(
    id="foundation.backfill",
    name="Feature Backfill",
    description="Generates a PIT features matrix from OHLCV data.",
    category="foundation",
)
def backfill_features_stage(candidates_path: str | None = None, output_path: str | None = None, lakehouse_dir: str | None = None):
    cand_p = Path(candidates_path) if candidates_path else None
    out_p = Path(output_path) if output_path else None
    lh_p = Path(lakehouse_dir) if lakehouse_dir else None

    service = BackfillService(lakehouse_dir=lh_p)
    service.run(candidates_path=cand_p, output_path=out_p)
    return True


class BackfillService:
    def __init__(self, lakehouse_dir: Path | None = None):
        settings = get_settings()
        self.lakehouse_dir = lakehouse_dir or settings.lakehouse_dir

    def _get_lakehouse_symbols(self) -> list[str]:
        """Returns all symbols currently present in the Lakehouse."""
        symbols = []
        for p in self.lakehouse_dir.glob("*_1d.parquet"):
            # BINANCE_BTCUSDT_1d.parquet -> BINANCE:BTCUSDT
            stem = p.stem.replace("_1d", "")
            if "_" in stem:
                parts = stem.split("_", 1)
                symbols.append(f"{parts[0]}:{parts[1]}")
        return sorted(symbols)

    def run(self, candidates_path: Path | None = None, output_path: Path | None = None):
        """
        Main execution flow.
        """
        settings = get_settings()
        out_p = output_path or (settings.lakehouse_dir / "features_matrix.parquet")

        # 1. Resolve Symbols (Phase 630: Full Coverage)
        lakehouse_symbols = self._get_lakehouse_symbols()

        if candidates_path and candidates_path.exists():
            with open(candidates_path, "r") as f:
                candidates = json.load(f)
            provided_symbols = list(set([c.get("physical_symbol") or c.get("symbol") for c in candidates]))

            # Audit Coverage
            missing_from_provided = set(lakehouse_symbols) - set(provided_symbols)
            if missing_from_provided:
                logger.warning(f"Feature Store Audit: {len(missing_from_provided)} symbols in Lakehouse but missing from candidates: {list(missing_from_provided)[:5]}...")

            symbols = provided_symbols
        else:
            logger.info("No candidates file provided. Scanning full Lakehouse for symbols.")
            symbols = lakehouse_symbols

        logger.info(f"Backfilling features for {len(symbols)} unique symbols...")

        all_features = {}

        # 2. Parallel Processing (Phase 470)
        use_parallel = os.getenv("TV_ORCH_PARALLEL") == "1"
        processed_results = {}  # Map of symbol -> file_path

        # Create a temp directory for individual feature files to avoid OOM in driver
        temp_features_dir = self.lakehouse_dir / "temp_features"
        temp_features_dir.mkdir(parents=True, exist_ok=True)

        if use_parallel:
            logger.info(f"Dispatching {len(symbols)} symbols to Ray cluster...")
            with RayComputeEngine() as engine:
                engine.ensure_initialized()
                futures = [_process_single_symbol_task.remote(s, self.lakehouse_dir, temp_features_dir) for s in symbols]
                results = ray.get(futures)

                for res in results:
                    if res:
                        symbol, path = res
                        processed_results[symbol] = path
        else:
            # Sequential Fallback
            for symbol in tqdm(symbols, desc="Processing Symbols"):
                res = _process_single_symbol(symbol, self.lakehouse_dir, temp_features_dir)
                if res:
                    symbol, path = res
                    processed_results[symbol] = path

        if not processed_results:
            logger.error("No ratings generated.")
            return

        # 3. Consolidation & Validation (Memory-efficient)
        logger.info(f"Consolidating features matrix from {len(processed_results)} temporary files...")

        from tradingview_scraper.pipelines.selection.base import FoundationHealthRegistry
        from tradingview_scraper.utils.features import FeatureConsistencyValidator

        registry = FoundationHealthRegistry(path=self.lakehouse_dir / "foundation_health.json")

        # We collect DataFrames for the final matrix, but we audit them one-by-one
        # to keep memory usage predictable during the audit phase.
        all_dfs = []
        intermediate_dfs = []
        for symbol, path in tqdm(processed_results.items(), desc="Auditing & Collecting"):
            try:
                df = pd.read_parquet(path)

                # Check for NaN density in 'recommend_all' (Phase 630 Audit)
                if "recommend_all" in df.columns:
                    val_series = df["recommend_all"]
                    is_degraded = FeatureConsistencyValidator.check_nan_density(val_series)
                    if is_degraded:
                        logger.warning(f"Feature Store: {symbol} has degraded feature density. Flagging.")
                        registry.update_status(symbol, status="toxic", reason="feature_nan_density")

                # Prepare for wide-matrix consolidation
                df.columns = pd.MultiIndex.from_product([[symbol], df.columns])
                all_dfs.append(df)

                # Incremental consolidation to bound peak memory (Task 099)
                if len(all_dfs) >= 500:
                    logger.info(f"Memory Guard: Performing intermediate consolidation of {len(all_dfs)} DataFrames")
                    intermediate_dfs.append(pd.concat(all_dfs, axis=1))
                    all_dfs = []
            except Exception as e:
                logger.error(f"Failed to load/audit {symbol} from {path}: {e}")

        # Collect any remaining DataFrames
        if all_dfs:
            intermediate_dfs.append(pd.concat(all_dfs, axis=1))
            all_dfs = []

        registry.save()

        if not intermediate_dfs:
            logger.error("No valid feature DataFrames collected for consolidation.")
            return

        # 4. Final Matrix Generation
        # This is the single point where memory usage will peak, but now bounded by intermediate chunks.
        logger.info(f"Performing final matrix concatenation from {len(intermediate_dfs)} intermediate chunks...")
        features_df = pd.concat(intermediate_dfs, axis=1)

        # Clear the list of intermediate DataFrames as soon as possible
        del intermediate_dfs

        # Drop rows that are all NaN (before any meaningful history started)
        features_df = features_df.dropna(how="all")

        # 5. Save Artifact
        out_p.parent.mkdir(parents=True, exist_ok=True)
        features_df.to_parquet(out_p)

        # Cleanup temp files
        import shutil

        try:
            shutil.rmtree(temp_features_dir)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp features directory: {e}")

        logger.info(f"Saved consolidated feature matrix to {out_p}")
        logger.info(f"Shape: {features_df.shape} | Hash: {get_df_hash(features_df)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", help="Path to portfolio_candidates.json")
    parser.add_argument("--output", help="Path to output features_matrix.parquet")
    parser.add_argument("--lakehouse", help="Path to lakehouse dir (optional)")

    args = parser.parse_args()

    lakehouse_arg = Path(args.lakehouse) if args.lakehouse else None
    output_arg = Path(args.output) if args.output else None
    cand_arg = Path(args.candidates) if args.candidates else None

    service = BackfillService(lakehouse_dir=lakehouse_arg)
    service.run(candidates_path=cand_arg, output_path=output_arg)
