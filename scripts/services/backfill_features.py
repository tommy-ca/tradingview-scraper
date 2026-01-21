import argparse
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import get_df_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backfill_features")


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

    def run(self, candidates_path: Path, output_path: Path):
        """
        Main execution flow.
        """
        if not candidates_path.exists():
            logger.error(f"Candidates file not found: {candidates_path}")
            return

        with open(candidates_path, "r") as f:
            candidates = json.load(f)

        # Extract unique physical symbols
        symbols = list(set([c.get("physical_symbol") or c.get("symbol") for c in candidates]))
        logger.info(f"Backfilling features for {len(symbols)} unique symbols...")

        all_features = {}

        for symbol in tqdm(symbols, desc="Processing Symbols"):
            safe_sym = symbol.replace(":", "_")
            file_path = self.lakehouse_dir / f"{safe_sym}_1d.parquet"

            if not file_path.exists():
                # logger.warning(f"Data not found for {symbol}")
                continue

            try:
                df = pd.read_parquet(file_path)
                # Normalize columns
                df.columns = [c.lower() for c in df.columns]

                # Ensure DatetimeIndex
                if "timestamp" in df.columns:
                    df = df.set_index("timestamp")
                elif "date" in df.columns:
                    df = df.set_index("date")

                if not isinstance(df.index, pd.DatetimeIndex):
                    # Intelligent Unit Detection
                    sample = df.index[0]
                    unit = "ns"  # Default
                    if isinstance(sample, (int, float, np.number)):
                        if sample < 2e10:  # Seconds (e.g. 1.7e9)
                            unit = "s"
                        elif sample < 2e13:  # Milliseconds (e.g. 1.7e12)
                            unit = "ms"
                        elif sample < 2e16:  # Microseconds
                            unit = "us"

                    df.index = pd.to_datetime(df.index, unit=unit)

                if df.index.tz is not None:
                    df.index = df.index.tz_convert(None)

                if "close" not in df.columns:
                    continue

                # Sort just in case
                df = df.sort_index()

                # Calculate Vectorized
                ma, osc, rating = self.calculate_technicals_vectorized(df)

                # Store
                all_features[(symbol, "recommend_ma")] = ma
                all_features[(symbol, "recommend_other")] = osc
                all_features[(symbol, "recommend_all")] = rating

            except Exception as e:
                logger.error(f"Failed to calc technicals for {symbol}: {e}")

        if not all_features:
            logger.error("No ratings generated.")
            return

        # Combine into Multi-Index DataFrame
        logger.info("Consolidating features matrix...")
        features_df = pd.DataFrame(all_features)
        features_df.columns.names = ["symbol", "feature"]

        # Ensure output dir exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        features_df.to_parquet(output_path)
        logger.info(f"Saved feature matrix to {output_path}")
        logger.info(f"Shape: {features_df.shape} | Hash: {get_df_hash(features_df)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="Path to portfolio_candidates.json")
    parser.add_argument("--output", required=True, help="Path to output features_matrix.parquet")
    parser.add_argument("--lakehouse", help="Path to lakehouse dir (optional)")

    args = parser.parse_args()

    lakehouse = Path(args.lakehouse) if args.lakehouse else None
    service = BackfillService(lakehouse_dir=lakehouse)
    service.run(Path(args.candidates), Path(args.output))
