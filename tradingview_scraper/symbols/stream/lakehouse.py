import logging
import os
from typing import List, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class LakehouseStorage:
    """
    Manages local Parquet-based storage for OHLCV data.
    Provides methods to save, load, and deduplicate historical candles.
    """

    def __init__(self, base_path: str = "data/lakehouse"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def _get_path(self, symbol: str, interval: str) -> str:
        # Sanitize symbol for filename (e.g. BINANCE:BTCUSDT -> BINANCE_BTCUSDT)
        safe_symbol = symbol.replace(":", "_")
        return os.path.join(self.base_path, f"{safe_symbol}_{interval}.parquet")

    def save_candles(self, symbol: str, interval: str, candles: List[dict]):
        """
        Saves candles to storage, merging with existing data and deduplicating.
        """
        if not candles:
            return

        file_path = self._get_path(symbol, interval)
        new_df = pd.DataFrame(candles)

        if os.path.exists(file_path):
            existing_df = pd.read_parquet(file_path)
            # Concatenate and deduplicate by timestamp
            df = pd.concat([existing_df, new_df])
            df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")
        else:
            df = new_df.sort_values("timestamp")

        df.to_parquet(file_path, index=False)
        logger.info(f"Saved {len(new_df)} candles for {symbol} ({interval}). Total records: {len(df)}")

    def load_candles(self, symbol: str, interval: str, start_ts: Optional[float] = None, end_ts: Optional[float] = None) -> pd.DataFrame:
        """
        Loads candles from storage within an optional timestamp range.
        """
        file_path = self._get_path(symbol, interval)
        if not os.path.exists(file_path):
            return pd.DataFrame()

        df = pd.read_parquet(file_path)

        if start_ts is not None:
            df = df[df["timestamp"] >= start_ts]
        if end_ts is not None:
            df = df[df["timestamp"] <= end_ts]

        return df.sort_values("timestamp")

    def get_last_timestamp(self, symbol: str, interval: str) -> Optional[float]:
        """
        Returns the newest timestamp in storage for a symbol.
        """
        file_path = self._get_path(symbol, interval)
        if not os.path.exists(file_path):
            return None

        # We can optimize this by only reading metadata if file is huge
        df = pd.read_parquet(file_path, columns=["timestamp"])
        if df.empty:
            return None
        return df["timestamp"].max()
