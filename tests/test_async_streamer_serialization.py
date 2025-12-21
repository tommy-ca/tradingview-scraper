import unittest
from unittest.mock import AsyncMock

from tradingview_scraper.symbols.stream.streamer_async import AsyncStreamer


class TestAsyncStreamerSerialization(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.streamer = AsyncStreamer()
        # Mock study map for indicator testing
        self.streamer.study_id_to_name_map = {"st9": "STD;RSI"}

    async def test_get_data_formatted(self):
        # Mock handler to return a raw OHLC packet
        mock_handler = AsyncMock()
        packet = {"m": "timescale_update", "p": [{}, {"sds_1": {"s": [{"i": 0, "v": [1600000000, 100.0, 105.0, 95.0, 102.0, 1000]}]}}]}
        mock_handler.get_next_message.side_effect = [packet, None]
        self.streamer.stream_obj = mock_handler

        gen = self.streamer.get_data()

        # We expect get_data to yield formatted dictionaries if updated
        # In current state, it yields the raw packet
        msg = await gen.__anext__()

        # If formatted, it should have "ohlc" or "indicator" keys
        self.assertIn("ohlc", msg)
        self.assertEqual(len(msg["ohlc"]), 1)
        self.assertEqual(msg["ohlc"][0]["close"], 102.0)

    def test_serialize_ohlc(self):
        packet = {"m": "timescale_update", "p": [{}, {"sds_1": {"s": [{"i": 0, "v": [1600000000, 100.0, 105.0, 95.0, 102.0, 1000]}]}}]}
        # In current state, _serialize_ohlc does not exist in AsyncStreamer
        # So this should fail with AttributeError
        serialized = self.streamer._serialize_ohlc(packet)

        expected = [{"index": 0, "timestamp": 1600000000, "open": 100.0, "high": 105.0, "low": 95.0, "close": 102.0, "volume": 1000}]
        self.assertEqual(serialized, expected)

    def test_extract_indicator_from_stream(self):
        # Create 11 points to pass the len > 10 check
        points = [{"i": i, "v": [1600000000 + i, 50.5 + i]} for i in range(11)]
        packet = {"m": "du", "p": [{}, {"st9": {"st": points}}]}
        extracted = self.streamer._extract_indicator_from_stream(packet)

        self.assertIn("STD;RSI", extracted)
        self.assertEqual(len(extracted["STD;RSI"]), 11)
        self.assertEqual(extracted["STD;RSI"][0]["index"], 0)
        self.assertEqual(extracted["STD;RSI"][0]["timestamp"], 1600000000)
        self.assertEqual(extracted["STD;RSI"][0]["0"], 50.5)


if __name__ == "__main__":
    unittest.main()
