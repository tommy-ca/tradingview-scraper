import logging
from datetime import datetime, timedelta
from typing import List, Union

from tradingview_scraper.symbols.stream import Streamer

logger = logging.getLogger(__name__)


class DataLoader:
    """
    A class to load historical data for backtesting using the Streamer API.
    Provides a standardized interface: load(symbol, start, end, interval).
    """

    TIMEFRAME_MINUTES = {"1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30, "45m": 45, "1h": 60, "2h": 120, "3h": 180, "4h": 240, "1d": 1440, "1w": 10080, "1M": 43200}

    def __init__(self, websocket_jwt_token: str = "unauthorized_user_token"):
        self.websocket_jwt_token = websocket_jwt_token

    def _calculate_candles_needed(self, start: datetime, end: datetime, interval: str) -> int:
        """
        Calculates the number of candles needed to cover the range from start to end.
        """
        if interval not in self.TIMEFRAME_MINUTES:
            raise ValueError(f"Unsupported interval: {interval}")

        # We need to calculate how many 'interval' units are between 'now' and 'start'
        # because the API returns the latest N candles.
        now = datetime.now()
        delta = now - start

        minutes_total = delta.total_seconds() / 60
        candles_count = int(minutes_total / self.TIMEFRAME_MINUTES[interval])

        # Add a buffer to ensure we cover the range even with gaps
        return max(candles_count + 10, 10)

    def load(self, exchange_symbol: str, start: Union[datetime, str], end: Union[datetime, str], interval: str = "1h") -> List[dict]:
        """
        Loads historical OHLCV data for a specific range.

        Args:
            exchange_symbol (str): Symbol in 'EXCHANGE:SYMBOL' format.
            start (datetime | str): Start date.
            end (datetime | str): End date.
            interval (str): Timeframe interval (e.g., '1m', '1h', '1d').

        Returns:
            List[dict]: List of OHLCV candles within the requested range.
        """
        if isinstance(start, str):
            start = datetime.fromisoformat(start)
        if isinstance(end, str):
            end = datetime.fromisoformat(end)

        parts = exchange_symbol.split(":")
        if len(parts) != 2:
            raise ValueError("Symbol must be in 'EXCHANGE:SYMBOL' format")

        exchange, symbol = parts[0], parts[1]

        n_candles = self._calculate_candles_needed(start, end, interval)
        logger.info(f"Requesting {n_candles} candles for {exchange_symbol} to cover range starting {start}")

        streamer = Streamer(export_result=True, websocket_jwt_token=self.websocket_jwt_token)
        try:
            res = streamer.stream(exchange, symbol, timeframe=interval, numb_price_candles=n_candles, auto_close=True)
            candles = res.get("ohlc", [])

            # Filter candles by range [start, end]
            start_ts = start.timestamp()
            end_ts = end.timestamp()

            filtered = [c for c in candles if start_ts <= c["timestamp"] <= end_ts]

            logger.info(f"Fetched {len(candles)} total, returned {len(filtered)} within range.")
            return filtered
        except Exception as e:
            logger.error(f"Failed to load historical data: {e}")
            return []


if __name__ == "__main__":
    # Quick demo
    logging.basicConfig(level=logging.INFO)
    loader = DataLoader()

    # Load last 24 hours of 1h data
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=1)

    data = loader.load("BINANCE:BTCUSDT", start_dt, end_dt, interval="1h")
    for candle in data[:5]:
        print(datetime.fromtimestamp(candle["timestamp"]), candle["close"])
