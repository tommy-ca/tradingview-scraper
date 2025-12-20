import logging
from datetime import datetime, timedelta
from typing import Union

import pandas as pd

from tradingview_scraper.symbols.stream.lakehouse import LakehouseStorage
from tradingview_scraper.symbols.stream.loader import DataLoader

logger = logging.getLogger(__name__)


class PersistentDataLoader:
    """
    A wrapper for DataLoader that manages local persistence via LakehouseStorage.
    Encapsulates the forward-accumulation pattern to build deep history over time.
    """

    def __init__(self, lakehouse_path: str = "data/lakehouse", websocket_jwt_token: str = "unauthorized_user_token"):
        self.loader = DataLoader(websocket_jwt_token=websocket_jwt_token)
        self.storage = LakehouseStorage(base_path=lakehouse_path)

    def sync(self, symbol: str, interval: str = "1h", depth: int = 1000) -> int:
        """
        Synchronizes local storage with the latest data from the API.
        Fetches the latest N candles and merges them into the lakehouse.

        Args:
            symbol (str): Symbol in 'EXCHANGE:SYMBOL' format.
            interval (str): Timeframe interval.
            depth (int): Number of candles to fetch for initial backfill or update.

        Returns:
            int: Number of new unique candles added.
        """
        last_ts = self.storage.get_last_timestamp(symbol, interval)

        # If we have data, we might only need a few candles,
        # but the API gives "Latest N" anyway, so we just fetch and merge.
        # Overlap is handled by deduplication in storage.save_candles.

        # Determine start date for logging info
        if last_ts:
            last_dt = datetime.fromtimestamp(last_ts)
            logger.info(f"Syncing {symbol} ({interval}) from last seen: {last_dt}")
        else:
            logger.info(f"Performing initial sync for {symbol} ({interval}) with depth {depth}")

        # Fetch latest data from API
        # We use a dummy range that results in 'depth' candles
        end_dt = datetime.now()
        # DataLoader calculates count based on start_dt.
        # We just want 'depth' candles, so we estimate a start_dt.
        start_dt = end_dt - timedelta(minutes=self.loader.TIMEFRAME_MINUTES[interval] * depth)
        # Note: we don't use DataLoader.load directly because we want the FULL N candles,
        # not a filtered range.
        # Let's use a simpler internal fetch or just use load with a broad range.

        from tradingview_scraper.symbols.stream import Streamer

        streamer = Streamer(export_result=True, websocket_jwt_token=self.loader.websocket_jwt_token)
        parts = symbol.split(":")
        res = streamer.stream(parts[0], parts[1], timeframe=interval, numb_price_candles=depth, auto_close=True)
        candles = res.get("ohlc", [])

        if candles:
            count_before = len(self.storage.load_candles(symbol, interval))
            self.storage.save_candles(symbol, interval, candles)
            count_after = len(self.storage.load_candles(symbol, interval))
            new_records = count_after - count_before
            logger.info(f"Sync complete. Added {new_records} new candles.")
            return new_records

        return 0

    def load(self, symbol: str, start: Union[datetime, str], end: Union[datetime, str], interval: str = "1h", force_api: bool = False) -> pd.DataFrame:
        """
        Loads data from local storage, falling back to API if range is missing.
        """
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        start_ts = start.timestamp()
        end_ts = end.timestamp()

        # 1. Check local storage
        df = self.storage.load_candles(symbol, interval, start_ts, end_ts)

        # 2. If data is missing or force_api, try to fetch from API
        # (Simple logic: if df is empty, we definitely need API)
        if df.empty or force_api:
            logger.info(f"Data for {symbol} range not found in local storage. Fetching from API...")
            api_candles = self.loader.load(symbol, start, end, interval)
            if api_candles:
                self.storage.save_candles(symbol, interval, api_candles)
                df = self.storage.load_candles(symbol, interval, start_ts, end_ts)

        return df
