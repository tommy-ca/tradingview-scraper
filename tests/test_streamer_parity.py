import unittest

from tradingview_scraper.symbols.stream.streamer import Streamer
from tradingview_scraper.symbols.stream.streamer_async import AsyncStreamer


class TestStreamerParity(unittest.TestCase):
    def setUp(self):
        self.sync_streamer = Streamer()
        self.async_streamer = AsyncStreamer()

        # Sync indicators
        self.sync_streamer.study_id_to_name_map = {"st9": "STD;RSI"}
        self.async_streamer.study_id_to_name_map = {"st9": "STD;RSI"}

    def test_ohlc_parity(self):
        packet = {"m": "timescale_update", "p": [{}, {"sds_1": {"s": [{"i": 0, "v": [1600000000, 100.0, 105.0, 95.0, 102.0, 1000]}]}}]}

        sync_out = self.sync_streamer._extract_ohlc_from_stream(packet)
        async_out = self.async_streamer._extract_ohlc_from_stream(packet)

        self.assertEqual(sync_out, async_out)
        self.assertEqual(sync_out[0]["close"], 102.0)

    def test_indicator_parity(self):
        # 11 points to satisfy len > 10 check
        points = [{"i": i, "v": [1600000000 + i, 50.5 + i]} for i in range(11)]
        packet = {"m": "du", "p": [{}, {"st9": {"st": points}}]}

        sync_out = self.sync_streamer._extract_indicator_from_stream(packet)
        async_out = self.async_streamer._extract_indicator_from_stream(packet)

        self.assertEqual(sync_out, async_out)
        self.assertIn("STD;RSI", sync_out)


if __name__ == "__main__":
    unittest.main()
