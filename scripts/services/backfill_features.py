import argparse
import json
import logging
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Optional, Tuple

import numpy as np
import pandas as pd
import pandera.errors as pa_errors
import ray
from tqdm import tqdm

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.contracts import FeatureStoreSchema
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash
from tradingview_scraper.utils.data_utils import ensure_utc_index
from tradingview_scraper.utils.predictability import rolling_permutation_entropy, rolling_rs
from tradingview_scraper.utils.security import SecurityUtils
from tradingview_scraper.utils.technicals import TechnicalRatings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


def _normalize_candidate_meta(meta: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if k is None:
            continue
        key = str(k).strip().lower().replace(".", "_")
        out[key] = v
    return out


def _backfill_worker(symbol: str, lakehouse_dir: Path, meta: dict[str, Any] | None = None) -> pd.DataFrame | None:
    """Compute per-symbol time-series features."""
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

    df = ensure_utc_index(df)
    if "close" not in df.columns:
        return None

    df = df.sort_index()
    meta_norm = _normalize_candidate_meta(meta or {})

    ma_val = meta_norm.get("recommend_ma")
    osc_val = meta_norm.get("recommend_other")
    rating_val = meta_norm.get("recommend_all")

    if ma_val is not None and osc_val is not None:
        ma = pd.Series(float(ma_val), index=df.index)
        osc = pd.Series(float(osc_val), index=df.index)
        rating = (ma + osc) / 2.0
    elif rating_val is not None:
        # Metadata priority: if Recommend.All is provided, do not compute technicals.
        # This keeps backfill deterministic in test environments where pandas_ta may be stubbed.
        rating = pd.Series(float(rating_val), index=df.index)
        ma = pd.Series(np.nan, index=df.index)
        osc = pd.Series(np.nan, index=df.index)
    else:
        ma = TechnicalRatings.calculate_recommend_ma_series(df)
        osc = TechnicalRatings.calculate_recommend_other_series(df)
        rating = TechnicalRatings.calculate_recommend_all_series(df)

    # CR-Hardening: NaN Sanitization (Phase 630)
    ma = ma.ffill(limit=3)
    osc = osc.ffill(limit=3)
    rating = rating.ffill(limit=3)

    close = df["close"].astype(float)
    rets = close.pct_change().to_numpy(dtype=np.float64)

    ent_20 = rolling_permutation_entropy(rets, window=20, order=5, delay=1)
    rs_60 = rolling_rs(rets, window=60)
    # Normalize R/S statistic into [0, 1] to keep feature ranges bounded.
    rs_60 = np.tanh(rs_60 / 10.0)

    feat_df = pd.DataFrame(
        {
            "recommend_ma": ma,
            "recommend_other": osc,
            "recommend_all": rating,
            "entropy_20": pd.Series(ent_20, index=df.index),
            "rs_60": pd.Series(rs_60, index=df.index),
        },
        index=df.index,
    )

    if meta_norm.get("adx") is not None:
        feat_df["adx"] = float(meta_norm["adx"])

    return ensure_utc_index(feat_df)


def _process_single_symbol(symbol: str, lakehouse_dir: Path, output_dir: Optional[Path] = None) -> Optional[Tuple[str, str]]:
    """Logic for calculating features for a single symbol."""
    try:
        feat_df = _backfill_worker(symbol, lakehouse_dir)
        if feat_df is None:
            return None

        if output_dir:
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

    def run(self, candidates_path: Path | None = None, output_path: Path | None = None, *, strict_scope: bool = False):
        """
        Main execution flow.
        """
        settings = get_settings()
        out_p = output_path or (settings.lakehouse_dir / "features_matrix.parquet")

        # 1. Resolve Symbols (Phase 630: Full Coverage)
        lakehouse_symbols = self._get_lakehouse_symbols()

        symbol_meta: dict[str, dict[str, Any]] = {}

        if strict_scope and (not candidates_path or not candidates_path.exists()):
            raise ValueError("strict_scope=True requires a valid candidates_path")

        if candidates_path and candidates_path.exists():
            with open(candidates_path, "r") as f:
                candidates = json.load(f)

            provided_symbols: list[str] = []
            for c in candidates:
                if not isinstance(c, dict):
                    continue
                sym = c.get("physical_symbol") or c.get("symbol")
                if sym:
                    provided_symbols.append(str(sym))
                    symbol_meta[str(sym)] = c

            provided_symbols = sorted(set(provided_symbols))

            # Audit Coverage
            missing_from_provided = set(lakehouse_symbols) - set(provided_symbols)
            if missing_from_provided:
                logger.warning(f"Feature Store Audit: {len(missing_from_provided)} symbols in Lakehouse but missing from candidates: {list(missing_from_provided)[:5]}...")

            symbols = provided_symbols
        else:
            logger.info("No candidates file provided. Scanning full Lakehouse for symbols.")
            symbols = lakehouse_symbols

        logger.info(f"Backfilling features for {len(symbols)} unique symbols...")

        # 2. Processing (Parallel optional)
        use_parallel = os.getenv("TV_ORCH_PARALLEL") == "1"
        processed_results: dict[str, str] = {}  # Map of key -> file_path

        # Create a temp directory for individual feature files to avoid OOM in driver
        temp_features_dir = self.lakehouse_dir / "temp_features"
        temp_features_dir.mkdir(parents=True, exist_ok=True)

        direct_n = 0

        def _persist_df(key: str, feat_df: pd.DataFrame, *, filename_hint: str) -> None:
            out_file = temp_features_dir / filename_hint
            feat_df = ensure_utc_index(feat_df)
            feat_df.to_parquet(out_file)
            processed_results[key] = str(out_file)

        if use_parallel:
            max_workers = int(os.getenv("TV_ORCH_CPUS", "0") or "0") or None
            with ProcessPoolExecutor(max_workers=max_workers) as ex:
                futures = {}
                for sym in symbols:
                    futures[ex.submit(_backfill_worker, sym, self.lakehouse_dir, symbol_meta.get(sym))] = sym

                for fut in tqdm(as_completed(futures), total=len(futures), desc="Processing Symbols"):
                    sym = futures[fut]
                    try:
                        res = fut.result()
                    except ValueError as e:
                        logger.error(f"Invalid symbol in candidates list: {sym} ({e})")
                        continue
                    if res is None:
                        continue
                    if not isinstance(res, pd.DataFrame):
                        res = pd.DataFrame(res)

                    if isinstance(res.columns, pd.MultiIndex) and res.columns.nlevels == 2:
                        key = f"direct_{direct_n}"
                        direct_n += 1
                        _persist_df(key, res, filename_hint=f"{key}.parquet")
                    else:
                        sym_safe = sym.replace(":", "_")
                        _persist_df(sym, res, filename_hint=f"{sym_safe}_features.parquet")
        else:
            for sym in tqdm(symbols, desc="Processing Symbols"):
                try:
                    res = _backfill_worker(sym, self.lakehouse_dir, symbol_meta.get(sym))
                except ValueError as e:
                    logger.error(f"Invalid symbol in candidates list: {sym} ({e})")
                    continue
                if res is None:
                    continue
                if not isinstance(res, pd.DataFrame):
                    res = pd.DataFrame(res)

                if isinstance(res.columns, pd.MultiIndex) and res.columns.nlevels == 2:
                    key = f"direct_{direct_n}"
                    direct_n += 1
                    _persist_df(key, res, filename_hint=f"{key}.parquet")
                else:
                    sym_safe = sym.replace(":", "_")
                    _persist_df(sym, res, filename_hint=f"{sym_safe}_features.parquet")

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
                df = ensure_utc_index(df)

                # Check for NaN density in 'recommend_all' (Phase 630 Audit)
                if "recommend_all" in df.columns:
                    val_series = df["recommend_all"]
                    is_degraded = FeatureConsistencyValidator.check_nan_density(val_series)
                    if is_degraded:
                        logger.warning(f"Feature Store: {symbol} has degraded feature density. Flagging.")
                        registry.update_status(symbol, status="toxic", reason="feature_nan_density")

                # Prepare for wide-matrix consolidation
                if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels == 2:
                    df.columns = df.columns.set_names(["symbol", "feature"])
                else:
                    df.columns = pd.MultiIndex.from_product([[symbol], df.columns], names=["symbol", "feature"])
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
        features_df = ensure_utc_index(features_df)

        # Clear the list of intermediate DataFrames as soon as possible
        del intermediate_dfs

        # Drop rows that are all NaN (before any meaningful history started)
        features_df = features_df.dropna(how="all")

        # Validation Step (Filter-and-Log)
        logger.info("Validating features against FeatureStoreSchema...")
        valid_symbols = []
        if isinstance(features_df.columns, pd.MultiIndex):
            features_df.columns = features_df.columns.set_names(["symbol", "feature"])
        unique_symbols = features_df.columns.get_level_values("symbol").unique()

        for sym in unique_symbols:
            try:
                sym_df = features_df.xs(sym, axis=1, level="symbol")
                if isinstance(sym_df, pd.Series):
                    sym_df = sym_df.to_frame()
                FeatureStoreSchema.validate(sym_df)
                valid_symbols.append(sym)
            except pa_errors.SchemaError as e:
                logger.warning(f"Schema Validation Failed for {sym}: {e}. Dropping symbol.")
                # Filter: Don't add to valid_symbols

        # Apply filter if any symbols were dropped
        if len(valid_symbols) < len(unique_symbols):
            logger.info(f"Dropped {len(unique_symbols) - len(valid_symbols)} invalid symbols.")
            features_df = features_df.loc[:, features_df.columns.get_level_values("symbol").isin(valid_symbols)]

        # 5. Merge with existing matrix (override on overlap)
        if out_p.exists():
            try:
                existing_df = pd.read_parquet(out_p)
                existing_df = ensure_utc_index(existing_df)
                if isinstance(existing_df.columns, pd.MultiIndex):
                    existing_df.columns = existing_df.columns.set_names(["symbol", "feature"])
            except Exception as e:
                logger.warning(f"Failed to load existing features matrix from {out_p}: {e}")
                existing_df = None

            if existing_df is not None:
                idx = existing_df.index.union(features_df.index)
                final_df = existing_df.reindex(idx)
                new_df = features_df.reindex(idx)
                for col in new_df.columns:
                    final_df[col] = new_df[col]
                features_df = final_df

        # 6. Save Artifact
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
