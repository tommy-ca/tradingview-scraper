import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp

from tradingview_scraper.symbols.screener import Screener
from tradingview_scraper.symbols.screener_async import AsyncScreener


class TestAsyncScreener(unittest.TestCase):
    def setUp(self):
        self.screener = AsyncScreener()

    def test_market_parity(self):
        # Verify AsyncScreener supports all markets that Screener supports
        sync_markets = set(Screener.SUPPORTED_MARKETS.keys())
        async_markets = set(self.screener.SUPPORTED_MARKETS.keys())
        self.assertEqual(sync_markets, async_markets)

    def test_default_columns_parity(self):
        # Verify default columns are consistent
        for market in ["crypto", "forex", "america"]:
            sync_cols = Screener()._get_default_columns(market)
            async_cols = self.screener._get_default_columns(market)
            self.assertEqual(sync_cols, async_cols)

    @patch("aiohttp.ClientSession.post")
    def test_screen_retry_on_429(self, mock_post):
        # Setup mock responses: first two fail with 429, third succeeds
        mock_fail = MagicMock()
        mock_fail.status = 429
        mock_fail.text = AsyncMock(return_value="Rate limit exceeded")

        mock_success = MagicMock()
        mock_success.status = 200
        mock_success.json = AsyncMock(return_value={"data": [{"s": "BINANCE:BTCUSDT", "d": [100]}]})

        mock_post.return_value.__aenter__.side_effect = [mock_fail, mock_fail, mock_success]

        async def run_test():
            async with aiohttp.ClientSession() as session:
                return await self.screener.screen(session, "crypto", [], ["close"])

        result = asyncio.run(run_test())

        self.assertEqual(result["status"], "success")
        self.assertEqual(mock_post.call_count, 3)

    @patch("aiohttp.ClientSession.post")
    @patch("tradingview_scraper.symbols.screener_async.save_json_file")
    def test_screen_export_json(self, mock_save_json, mock_post):
        # Setup mock response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"data": [{"s": "BINANCE:BTCUSDT", "d": [100]}]})
        mock_post.return_value.__aenter__.return_value = mock_resp

        # Initialize screener with export enabled
        self.screener.export_result = True
        self.screener.export_type = "json"

        async def run_test():
            async with aiohttp.ClientSession() as session:
                return await self.screener.screen(session, "crypto", [], ["close"])

        asyncio.run(run_test())

        mock_save_json.assert_called_once()

    @patch("aiohttp.ClientSession.post")
    def test_screen_many(self, mock_post):
        # Setup mock response
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value={"data": [{"s": "BINANCE:BTCUSDT", "d": [100]}]})

        # mock_post is a context manager
        mock_post.return_value.__aenter__.return_value = mock_resp

        payloads = [{"market": "crypto", "filters": [], "columns": ["close"]}, {"market": "crypto", "filters": [], "columns": ["close"]}]

        results = asyncio.run(self.screener.screen_many(payloads))

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[0]["data"][0]["symbol"], "BINANCE:BTCUSDT")


if __name__ == "__main__":
    unittest.main()
