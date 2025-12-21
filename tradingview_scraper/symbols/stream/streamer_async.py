import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

from tradingview_scraper.symbols.stream.retry_async import AsyncRetryHandler
from tradingview_scraper.symbols.stream.stream_handler_async import AsyncStreamHandler
from tradingview_scraper.symbols.stream.utils import fetch_indicator_metadata, validate_symbols

logger = logging.getLogger(__name__)


class AsyncStreamer:
    """
    Asynchronous version of the Streamer class.
    """

    def __init__(
        self,
        export_result: bool = False,
        export_type: str = "json",
        websocket_jwt_token: str = "unauthorized_user_token",
        max_retries: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
    ):
        self.export_result = export_result
        self.export_type = export_type
        self.websocket_jwt_token = websocket_jwt_token
        self.retry_handler = AsyncRetryHandler(max_retries=max_retries, initial_delay=initial_delay, max_delay=max_delay, backoff_factor=backoff_factor)
        self.study_id_to_name_map = {}
        self.ws_url = "wss://data.tradingview.com/socket.io/websocket?from=chart%2FVEPYsueI%2F&type=chart"
        self.stream_obj = AsyncStreamHandler(websocket_url=self.ws_url, jwt_token=websocket_jwt_token)

        self._current_subscription: Optional[Tuple[str, str, int]] = None
        self._current_indicators: Optional[List[Tuple[str, str]]] = None

    async def _add_symbol_to_sessions(self, quote_session: str, chart_session: str, exchange_symbol: str, timeframe: str = "1m", numb_candles: int = 10):
        self._current_subscription = (exchange_symbol, timeframe, numb_candles)
        timeframe_map = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30", "45m": "45", "1h": "60", "2h": "120", "3h": "180", "4h": "240", "1d": "1D", "1w": "1W", "1M": "1M"}
        resolve_symbol = json.dumps({"adjustment": "splits", "symbol": exchange_symbol})
        await self.stream_obj.send_message("quote_add_symbols", [quote_session, f"={resolve_symbol}"])
        await self.stream_obj.send_message("resolve_symbol", [chart_session, "sds_sym_1", f"={resolve_symbol}"])
        await self.stream_obj.send_message("create_series", [chart_session, "sds_1", "s1", "sds_sym_1", timeframe_map.get(timeframe, "1"), numb_candles, ""])
        await self.stream_obj.send_message("quote_fast_symbols", [quote_session, exchange_symbol])

    async def _add_indicators(self, indicators: List[Tuple[str, str]]):
        self._current_indicators = indicators
        for idx, (indicator_id, indicator_version) in enumerate(indicators):
            logger.info(f"Processing indicator: {indicator_id}")

            ind_study = fetch_indicator_metadata(script_id=indicator_id, script_version=indicator_version, chart_session=self.stream_obj.chart_session)

            if not ind_study or "p" not in ind_study:
                logger.error(f"Failed to fetch metadata for {indicator_id}")
                continue

            study_id = f"st{9 + idx}"
            ind_study["p"][1] = study_id
            self.study_id_to_name_map[study_id] = indicator_id

            await self.stream_obj.send_message("create_study", ind_study["p"])
            await self.stream_obj.send_message("quote_hibernate_all", [self.stream_obj.quote_session])

    async def get_data(self) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields parsed data packets from the WebSocket handler with reconnection support.
        """
        attempt = 0
        while True:
            try:
                while True:
                    msg = await self.stream_obj.get_next_message()
                    if msg is None:  # Sentinel for connection lost
                        logger.error("WebSocket connection lost. Attempting to reconnect...")
                        break
                    yield msg
                    attempt = 0  # Reset attempt on success

                # Reconnection logic
                if attempt >= self.retry_handler.max_retries:
                    logger.error("Max retries reached. Stopping stream.")
                    break

                await self.retry_handler.sleep(attempt)
                attempt += 1

                # Re-establish connection
                self.stream_obj = AsyncStreamHandler(websocket_url=self.ws_url, jwt_token=self.websocket_jwt_token)
                await self.stream_obj.connect()
                await self.stream_obj.start_listening()

                # Re-subscribe
                if self._current_subscription:
                    await self._add_symbol_to_sessions(self.stream_obj.quote_session, self.stream_obj.chart_session, *self._current_subscription)
                if self._current_indicators:
                    await self._add_indicators(self._current_indicators)

            except Exception as e:
                logger.error(f"Failed to reconnect: {e}")
                if attempt >= self.retry_handler.max_retries:
                    break
                attempt += 1
                await self.retry_handler.sleep(attempt)

    async def stream(
        self, exchange: str, symbol: str, timeframe: str = "1m", numb_price_candles: int = 10, indicators: Optional[List[Tuple[str, str]]] = None, auto_close: bool = False
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Starts the async stream and returns the data generator.
        """
        exchange_symbol = f"{exchange}:{symbol}"
        validate_symbols(exchange_symbol)

        await self.stream_obj.connect()
        await self.stream_obj.start_listening()

        await self._add_symbol_to_sessions(self.stream_obj.quote_session, self.stream_obj.chart_session, exchange_symbol, timeframe, numb_price_candles)

        if indicators:
            await self._add_indicators(indicators)

        return self.get_data()

    async def close(self):
        await self.stream_obj.close()
