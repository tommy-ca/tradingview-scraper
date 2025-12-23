import logging
from datetime import datetime, timedelta
from typing import Optional, Union

import pandas as pd

from tradingview_scraper.symbols.stream.lakehouse import LakehouseStorage
from tradingview_scraper.symbols.stream.loader import DataLoader
from tradingview_scraper.symbols.stream.metadata import MetadataCatalog

logger = logging.getLogger(__name__)


class PersistentDataLoader:
    """
    A wrapper for DataLoader that manages local persistence via LakehouseStorage.
    Encapsulates the forward-accumulation pattern to build deep history over time.
    """

    def __init__(self, lakehouse_path: str = "data/lakehouse", websocket_jwt_token: str = "unauthorized_user_token"):
        self.loader = DataLoader(websocket_jwt_token=websocket_jwt_token)
        self.storage = LakehouseStorage(base_path=lakehouse_path)
        self.catalog = MetadataCatalog(base_path=lakehouse_path)

    def _ensure_metadata(self, symbol: str):
        """Checks if metadata exists, otherwise attempts to fetch it."""
        if self.catalog.get_instrument(symbol):
            return

        logger.info(f"Metadata missing for {symbol}. Triggering auto-enrichment...")
        try:
            from tradingview_scraper.symbols.overview import Overview

            # Fetch structural and descriptive metadata
            fields = ["pricescale", "minmov", "currency", "base_currency", "exchange", "type", "subtype", "description", "sector", "industry", "country"]

            ov = Overview()
            res = ov.get_symbol_overview(symbol, fields=fields)

            if res["status"] == "success":
                data = res["data"]
                pricescale = data.get("pricescale", 1)
                minmov = data.get("minmov", 1)

                record = {
                    "symbol": symbol,
                    "exchange": data.get("exchange"),
                    "base": data.get("base_currency"),
                    "quote": data.get("currency"),
                    "type": data.get("type"),
                    "subtype": data.get("subtype"),
                    "description": data.get("description"),
                    "sector": data.get("sector"),
                    "industry": data.get("industry"),
                    "country": data.get("country"),
                    "pricescale": pricescale,
                    "minmov": minmov,
                    "tick_size": minmov / pricescale if pricescale else None,
                    "timezone": "UTC",
                    "session": "24x7",
                    "active": True,
                }
                self.catalog.upsert_symbols([record])
                logger.info(f"Metadata enriched for {symbol}.")
            else:
                logger.warning(f"Could not fetch metadata for {symbol}: {res.get('error')}")

        except Exception as e:
            logger.error(f"Failed to auto-enrich metadata for {symbol}: {e}")

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
        # Ensure metadata exists before syncing data
        self._ensure_metadata(symbol)

        last_ts = self.storage.get_last_timestamp(symbol, interval)

        if last_ts:
            last_dt = datetime.fromtimestamp(last_ts)
            logger.info(f"Syncing {symbol} ({interval}) from last seen: {last_dt}")
        else:
            logger.info(f"Performing initial sync for {symbol} ({interval}) with depth {depth}")

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(minutes=self.loader.TIMEFRAME_MINUTES[interval] * depth)

        from tradingview_scraper.symbols.stream import Streamer

        streamer = Streamer(export_result=True, websocket_jwt_token=self.loader.websocket_jwt_token)
        parts = symbol.split(":")
        res = streamer.stream(parts[0], parts[1], timeframe=interval, numb_price_candles=depth, auto_close=True)
        candles = res.get("ohlc", []) if isinstance(res, dict) else []

        if candles:
            count_before = len(self.storage.load_candles(symbol, interval))
            self.storage.save_candles(symbol, interval, candles)
            count_after = len(self.storage.load_candles(symbol, interval))
            new_records = count_after - count_before
            logger.info(f"Sync complete. Added {new_records} new candles.")
            return new_records

        return 0

    def repair(self, symbol: str, interval: str = "1h", max_depth: Optional[int] = None) -> int:
        """
        Detects and attempts to fill gaps in local storage for a symbol.
        """
        gaps = self.storage.detect_gaps(symbol, interval)
        if not gaps:
            logger.info(f"No gaps detected for {symbol} ({interval}).")
            return 0

        total_filled = 0
        for gap_start, gap_end in gaps:
            now_ts = datetime.now().timestamp()
            diff_mins = (now_ts - gap_start) / 60
            depth = int(diff_mins / self.loader.TIMEFRAME_MINUTES[interval]) + 5

            if depth > 8500:
                logger.warning(f"Gap at {datetime.fromtimestamp(gap_start)} is too deep ({depth} candles). Max reach is ~8500.")
                depth = 8500

            if max_depth and depth > max_depth:
                logger.info(f"Gap depth {depth} capped to limit {max_depth}.")
                depth = max_depth

            logger.info(f"Attempting to fill gap: {datetime.fromtimestamp(gap_start)} to {datetime.fromtimestamp(gap_end)} (Depth: {depth})")
            filled = self.sync(symbol, interval, depth=depth)
            total_filled += filled

        return total_filled

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

        df = self.storage.load_candles(symbol, interval, start_ts, end_ts)

        if df.empty or force_api:
            logger.info(f"Data for {symbol} range not found in local storage. Fetching from API...")
            api_candles = self.loader.load(symbol, start, end, interval)
            if api_candles:
                self.storage.save_candles(symbol, interval, api_candles)
                df = self.storage.load_candles(symbol, interval, start_ts, end_ts)

        return df
