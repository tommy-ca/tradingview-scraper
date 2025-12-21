import os
import shutil
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tradingview_scraper.pipeline import QuantitativePipeline


class TestQuantitativePipeline(unittest.TestCase):
    def setUp(self):
        self.base_path = ".gemini/tmp/test_pipeline_lakehouse"
        if os.path.exists(self.base_path):
            shutil.rmtree(self.base_path)
        self.pipeline = QuantitativePipeline(lakehouse_path=self.base_path)

    @patch("tradingview_scraper.pipeline.AsyncScreener.screen_many", new_callable=AsyncMock)
    @patch("tradingview_scraper.pipeline.FuturesUniverseSelector")
    @patch("tradingview_scraper.pipeline.load_config")
    def test_run_discovery_async(self, mock_load_config, mock_selector_cls, mock_screen_many):
        # Setup mock config
        mock_load_config.return_value = MagicMock()

        # Setup mock selector for dry_run
        mock_selector = MagicMock()
        mock_selector.run.return_value = {"payloads": [{"market": "crypto"}]}
        mock_selector.process_data.return_value = {"status": "success", "data": [{"symbol": "BINANCE:BTCUSDT"}]}
        mock_selector_cls.return_value = mock_selector

        # Setup mock results from AsyncScreener
        mock_screen_many.return_value = [{"status": "success", "data": [{"symbol": "BTC_RAW"}]}]

        configs = ["configs/crypto_cex_trend_binance_spot_daily_long.yaml"]
        signals = self.pipeline.run_discovery(configs)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["symbol"], "BINANCE:BTCUSDT")
        self.assertEqual(signals[0]["direction"], "LONG")

        # Verify dry_run was used
        mock_selector.run.assert_called_with(dry_run=True)
        # Verify process_data was used with results from screen_many
        mock_selector.process_data.assert_called()

    @patch("tradingview_scraper.pipeline.QuantitativePipeline.run_discovery")
    def test_run_full_pipeline_success(self, mock_run_discovery):
        mock_run_discovery.return_value = [{"symbol": "BTC", "direction": "LONG"}]

        result = self.pipeline.run_full_pipeline(["configs/test.yaml"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total_signals"], 1)

    @patch("tradingview_scraper.pipeline.QuantitativePipeline.run_discovery")
    def test_run_full_pipeline_no_signals(self, mock_run_discovery):
        mock_run_discovery.return_value = []

        result = self.pipeline.run_full_pipeline(["configs/test.yaml"])
        self.assertEqual(result["status"], "no_signals")

    def tearDown(self):
        if os.path.exists(self.base_path):
            shutil.rmtree(self.base_path)


if __name__ == "__main__":
    unittest.main()
