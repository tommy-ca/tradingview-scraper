import os
import shutil
import unittest
from unittest.mock import MagicMock, patch

from tradingview_scraper.pipeline import QuantitativePipeline


class TestQuantitativePipeline(unittest.TestCase):
    def setUp(self):
        self.base_path = ".gemini/tmp/test_pipeline_lakehouse"
        if os.path.exists(self.base_path):
            shutil.rmtree(self.base_path)
        self.pipeline = QuantitativePipeline(lakehouse_path=self.base_path)

    @patch("tradingview_scraper.pipeline.FuturesUniverseSelector")
    @patch("tradingview_scraper.pipeline.load_config")
    def test_run_discovery(self, mock_load_config, mock_selector_cls):
        # Setup mock config
        mock_load_config.return_value = MagicMock()

        # Setup mock selector
        mock_selector = MagicMock()
        mock_selector.run.return_value = {"status": "success", "data": [{"symbol": "BINANCE:BTCUSDT"}]}
        mock_selector_cls.return_value = mock_selector

        configs = ["configs/crypto_cex_trend_binance_spot_daily_long.yaml"]
        signals = self.pipeline.run_discovery(configs)

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["symbol"], "BINANCE:BTCUSDT")
        self.assertEqual(signals[0]["direction"], "LONG")

    @patch("tradingview_scraper.pipeline.FuturesUniverseSelector")
    @patch("tradingview_scraper.pipeline.load_config")
    def test_run_discovery_failure(self, mock_load_config, mock_selector_cls):
        mock_load_config.return_value = MagicMock()
        mock_selector = MagicMock()
        mock_selector.run.return_value = {"status": "failed", "error": "API Timeout"}
        mock_selector_cls.return_value = mock_selector

        signals = self.pipeline.run_discovery(["configs/fail.yaml"])
        self.assertEqual(len(signals), 0)

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
