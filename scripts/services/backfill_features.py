import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
from tqdm import tqdm

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


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

    def calculate_technicals_vectorized(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Calculates composite Technical Ratings for the entire history at once.
        Returns (ma_rating, osc_rating, all_rating)
        """
        close = df["close"]

        # --- Moving Averages (Trend) ---
        sma20 = close.rolling(window=20).mean()
        sma50 = close.rolling(window=50).mean()
        sma200 = close.rolling(window=200).mean()
        ema20 = close.ewm(span=20, adjust=False).mean()

        # 0.5 to 1.0 = Buy
        ma_score = pd.Series(0.0, index=df.index)
        ma_score += (close > sma20).astype(float) * 0.25
        ma_score += (close > sma50).astype(float) * 0.25
        ma_score += (close > sma200).astype(float) * 0.25
        ma_score += (ema20 > sma20).astype(float) * 0.25

        # --- Oscillators (Mean Reversion / Momentum) ---
        # RSI 14
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100 - (100 / (1 + rs))

        # MACD (12, 26, 9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()

        osc_score = pd.Series(0.0, index=df.index)

        # RSI Logic: <30 Buy (+1), >70 Sell (-1), else Neutral
        osc_score += np.where(rsi < 30, 1.0, np.where(rsi > 70, -1.0, 0.0))

        # MACD Logic: MACD > Signal Buy (+1), else Sell (-1)
        osc_score += np.where(macd > signal, 1.0, -1.0)

        # Normalize Oscillator Score (-2 to 2 -> -1 to 1)
        osc_score = osc_score / 2.0

        # --- Composite Rating ---
        # Map Trend (0..1) -> (-1..1) for combination
        trend_norm = (ma_score * 2.0) - 1.0

        # Final Rating
        all_rating = (trend_norm + osc_score) / 2.0

        return ma_score, osc_score, all_rating

    def _get_lakehouse_symbols(self) -> List[str]:
        """Returns all symbols currently present in the Lakehouse."""
        symbols = []
        for p in self.lakehouse_dir.glob("*_1d.parquet"):
            # BINANCE_BTCUSDT_1d.parquet -> BINANCE:BTCUSDT
            stem = p.stem.replace("_1d", "")
            if "_" in stem:
                parts = stem.split("_", 1)
                symbols.append(f"{parts[0]}:{parts[1]}")
        return sorted(symbols)

    def run(self, candidates_path: Optional[Path] = None, output_path: Optional[Path] = None):
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

        for symbol in tqdm(symbols, desc="Processing Symbols"):
            safe_sym = symbol.replace(":", "_")
            file_path = self.lakehouse_dir / f"{safe_sym}_1d.parquet"

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

                if df.index.tz is not None:
                    df.index = df.index.tz_convert(None)

                if "close" not in df.columns:
                    continue

                df = df.sort_index()

                # Calculate Technicals
                ma, osc, rating = self.calculate_technicals_vectorized(df)

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
        from tradingview_scraper.utils.features import FeatureConsistencyValidator
        from tradingview_scraper.pipelines.selection.base import FoundationHealthRegistry

        registry = FoundationHealthRegistry(path=self.lakehouse_dir / "foundation_health.json")

        for symbol in symbols:
            # Check for NaN density in 'recommend_all'
            if (symbol, "recommend_all") in features_df.columns:
                series = features_df[(symbol, "recommend_all")]
                is_degraded = FeatureConsistencyValidator.check_nan_density(series)
                if is_degraded:
                    logger.warning(f"Feature Store: {symbol} has degraded feature density. Flagging.")
                    registry.update_status(symbol, status="toxic", reason="feature_nan_density")

        registry.save()

        # 4. Data Contract Enforcement (Pandera)
        try:
            from tradingview_scraper.pipelines.contracts import FeatureStoreSchema
            import pandera as pa

            # We need to un-pivot for FeatureStoreSchema validation or use a different schema
            # For now we use the matrix schema directly or skip if not ready.
            pass
        except ImportError:
            logger.warning("Pandera not available for feature validation.")

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

    service = BackfillService(lakehouse_dir=lakehouse_arg)
    service.run(candidates_path=cand_arg, output_path=output_arg)
