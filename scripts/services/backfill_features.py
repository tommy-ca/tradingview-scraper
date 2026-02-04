import argparse
import json
import logging
from pathlib import Path
from typing import cast

import pandas as pd
from tqdm import tqdm

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash
from tradingview_scraper.utils.security import SecurityUtils
from tradingview_scraper.utils.technicals import TechnicalRatings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


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

    # Call the functional implementation directly
    backfill_features(candidates_path=cand_p, output_path=out_p, lakehouse_dir=lh_p)
    return True


def _get_lakehouse_symbols(lakehouse_dir: Path) -> list[str]:
    """Returns all symbols currently present in the Lakehouse."""
    symbols = []
    for p in lakehouse_dir.glob("*_1d.parquet"):
        # BINANCE_BTCUSDT_1d.parquet -> BINANCE:BTCUSDT
        stem = p.stem.replace("_1d", "")
        if "_" in stem:
            parts = stem.split("_", 1)
            symbols.append(f"{parts[0]}:{parts[1]}")
    return sorted(symbols)


def backfill_features(candidates_path: Path | None = None, output_path: Path | None = None, lakehouse_dir: Path | None = None):
    """
    Main execution flow.
    """
    settings = get_settings()
    lakehouse_path = lakehouse_dir or settings.lakehouse_dir
    out_p = output_path or (settings.lakehouse_dir / "features_matrix.parquet")

    # 1. Resolve Symbols (Phase 630: Full Coverage)
    lakehouse_symbols = _get_lakehouse_symbols(lakehouse_path)

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

    for symbol in tqdm(symbols, desc="Processing Symbols"):
        try:
            file_path = SecurityUtils.get_safe_path(lakehouse_path, symbol)
        except ValueError as e:
            logger.error(f"Security error for {symbol}: {e}")
            continue

        if not file_path.exists():
            continue

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

            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC")
            else:
                df.index = df.index.tz_convert("UTC")

            if "close" not in df.columns:
                continue

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

            # Store
            all_features[(symbol, "recommend_ma")] = ma
            all_features[(symbol, "recommend_other")] = osc
            all_features[(symbol, "recommend_all")] = rating

        except Exception as e:
            logger.error(f"Failed to calc technicals for {symbol}: {e}")

    if not all_features:
        logger.error("No ratings generated.")
        return

    # 2. Consolidation & Validation
    logger.info("Consolidating features matrix...")
    features_df = pd.DataFrame(all_features)
    features_df.columns.names = ["symbol", "feature"]

    # Drop rows that are all NaN (before any meaningful history started)
    features_df = features_df.dropna(how="all")

    # 3. PIT Consistency Audit (Phase 630)
    from tradingview_scraper.pipelines.selection.base import FoundationHealthRegistry
    from tradingview_scraper.utils.features import FeatureConsistencyValidator

    registry = FoundationHealthRegistry(path=lakehouse_path / "foundation_health.json")

    for symbol in symbols:
        # Check for NaN density in 'recommend_all'
        if (symbol, "recommend_all") in features_df.columns:
            val_series = features_df[(symbol, "recommend_all")]
            if isinstance(val_series, pd.DataFrame):
                val_series = val_series.iloc[:, 0]

            is_degraded = FeatureConsistencyValidator.check_nan_density(cast(pd.Series, val_series))
            if is_degraded:
                logger.warning(f"Feature Store: {symbol} has degraded feature density. Flagging.")
                registry.update_status(symbol, status="toxic", reason="feature_nan_density")

    registry.save()

    # 4. Save Artifact
    # Ensure output dir exists
    out_p.parent.mkdir(parents=True, exist_ok=True)
    features_df.to_parquet(out_p)

    logger.info(f"Saved feature matrix to {out_p}")
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

    backfill_features(candidates_path=cand_arg, output_path=output_arg, lakehouse_dir=lakehouse_arg)
