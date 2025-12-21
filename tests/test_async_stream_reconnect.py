import unittest
from unittest.mock import AsyncMock, patch

from tradingview_scraper.symbols.stream.streamer_async import AsyncStreamer


class TestAsyncStreamerReconnect(unittest.IsolatedAsyncioTestCase):
    @patch("tradingview_scraper.symbols.stream.streamer_async.AsyncStreamHandler")
    async def test_streamer_reconnects_async(self, MockHandler):
        mock_handler = MockHandler.return_value
        mock_handler.connect = AsyncMock()
        mock_handler.start_listening = AsyncMock()
        mock_handler.send_message = AsyncMock()

        # Mock get_next_message to simulate data, then a "connection lost" (returning None), then data again
        mock_handler.get_next_message = AsyncMock(
            side_effect=[
                {"m": "timescale_update", "p": []},
                None,  # Sentinel for connection lost
                {"m": "timescale_update", "p": []},
            ]
        )

        streamer = AsyncStreamer()
        # Mock sleep to avoid delay
        with patch("asyncio.sleep", new_callable=AsyncMock):
            gen = await streamer.stream(exchange="BINANCE", symbol="BTCUSDT")

            # First packet
            pkt1 = await gen.__anext__()
            self.assertEqual(pkt1["m"], "timescale_update")

            # Second packet - should trigger reconnect internally and then return the next packet
            pkt2 = await gen.__anext__()
            self.assertEqual(pkt2["m"], "timescale_update")

            # Verify MockHandler was initialized/connected twice
            self.assertEqual(mock_handler.connect.call_count, 2)


if __name__ == "__main__":
    unittest.main()
