import logging
import os
from typing import List, Optional

import pandas as pd

from tradingview_scraper.symbols.stream.metadata import DataProfile

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

        try:
            df = pd.read_parquet(file_path)
            if not isinstance(df, pd.DataFrame):
                return pd.DataFrame()

            if start_ts is not None:
                df = df[df["timestamp"] >= start_ts]
            if end_ts is not None:
                df = df[df["timestamp"] <= end_ts]
            result_df = pd.DataFrame(df).sort_values(by="timestamp")
            return result_df
        except Exception as e:
            logger.error(f"Error loading candles for {symbol}: {e}")
            return pd.DataFrame()

    def get_last_timestamp(self, symbol: str, interval: str) -> Optional[float]:
        """
        Returns the newest timestamp in storage for a symbol.
        """
        file_path = self._get_path(symbol, interval)
        if not os.path.exists(file_path):
            return None

        try:
            df = pd.read_parquet(file_path, columns=["timestamp"])
            if df.empty:
                return None

            ts = df["timestamp"].max()
            if hasattr(ts, "item"):  # Handle numpy types
                ts = ts.item()
            return float(ts)  # type: ignore
        except Exception:
            return None

        try:
            df = pd.read_parquet(file_path, columns=["timestamp"])
            if df.empty:
                return None

            ts = df["timestamp"].max()
            if hasattr(ts, "item"):  # Handle numpy types
                ts = ts.item()
            return float(ts)
        except Exception:
            return None

    def contains_timestamp(self, symbol: str, interval: str, timestamp: float) -> bool:
        """
        Efficiently checks if a specific timestamp exists in storage for a symbol.
        """
        file_path = self._get_path(symbol, interval)
        if not os.path.exists(file_path):
            return False

        # Read only the timestamp column to check existence
        df = pd.read_parquet(file_path, columns=["timestamp"])
        if df.empty:
            return False
        return timestamp in df["timestamp"].values

    def detect_gaps(self, symbol: str, interval: str, profile: DataProfile = DataProfile.UNKNOWN, start_ts: Optional[float] = None) -> List[tuple]:
        """
        Identifies missing data points in the historical time-series.

        Args:
            symbol (str): Symbol name.
            interval (str): Timeframe interval.
            profile (DataProfile): Asset class profile for market-aware filtering.
            start_ts (Optional[float]): Only check for gaps after this timestamp.

        Returns:
            List[tuple]: List of (start_missing_ts, end_missing_ts) gaps.
        """
        df = self.load_candles(symbol, interval, start_ts=start_ts)
        if df.empty or len(df) < 2:
            return []

        # Expected interval in seconds
        from tradingview_scraper.symbols.stream.loader import DataLoader
        from tradingview_scraper.symbols.stream.metadata import get_exchange_calendar

        interval_mins = DataLoader.TIMEFRAME_MINUTES.get(interval)
        if not interval_mins:
            logger.error(f"Unknown interval for gap detection: {interval}")
            return []

        expected_diff = interval_mins * 60
        gaps = []

        # Pre-load calendar for the specific symbol
        cal = get_exchange_calendar(symbol, profile)

        timestamps = df["timestamp"].tolist()
        for i in range(1, len(timestamps)):
            diff = timestamps[i] - timestamps[i - 1]
            if diff > expected_diff * 1.5:  # Allow some tolerance
                gap_start = timestamps[i - 1] + expected_diff
                gap_end = timestamps[i] - expected_diff

                # Market-aware filtering
                if profile != DataProfile.CRYPTO:
                    start_dt = pd.Timestamp(gap_start, unit="s")
                    end_dt = pd.Timestamp(gap_end, unit="s")

                    # Skip gaps if the market was closed according to its institutional schedule
                    if interval == "1d":
                        # Check if there are any valid trading sessions in this range
                        try:
                            sessions = cal.sessions_in_range(start_dt.normalize(), end_dt.normalize())
                            if len(sessions) == 0:
                                continue
                        except Exception:
                            # Fallback if range is weird or outside calendar bounds
                            pass

                gaps.append((gap_start, gap_end))

        if gaps:
            logger.info(f"Detected {len(gaps)} gaps for {symbol} ({interval}).")
        return gaps
