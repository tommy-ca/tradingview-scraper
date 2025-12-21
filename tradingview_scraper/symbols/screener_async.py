import asyncio
import logging
from typing import Any, Dict, List, Optional

import aiohttp

from tradingview_scraper.symbols.utils import generate_user_agent

logger = logging.getLogger(__name__)


class AsyncScreener:
    """
    Asynchronous version of the Screener for high-performance scanning.
    """

    SUPPORTED_MARKETS = {
        "america": "https://scanner.tradingview.com/america/scan",
        "crypto": "https://scanner.tradingview.com/crypto/scan",
        "forex": "https://scanner.tradingview.com/forex/scan",
        "cfd": "https://scanner.tradingview.com/cfd/scan",
        "futures": "https://scanner.tradingview.com/futures/scan",
        "global": "https://scanner.tradingview.com/global/scan",
    }

    def __init__(self):
        self.headers = {"User-Agent": generate_user_agent()}

    async def screen(
        self,
        session: aiohttp.ClientSession,
        market: str,
        filters: List[Dict[str, Any]],
        columns: List[str],
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        limit: int = 50,
        range_start: int = 0,
    ) -> Dict:
        """Perform a single asynchronous screen request."""
        url = self.SUPPORTED_MARKETS.get(market)
        if not url:
            return {"status": "failed", "error": f"Unsupported market: {market}"}

        payload = {
            "columns": columns,
            "filter": filters,
            "options": {"lang": "en"},
            "range": [range_start, range_start + limit],
        }
        if sort_by:
            payload["sort"] = {"sortBy": sort_by, "sortOrder": sort_order}

        try:
            async with session.post(url, json=payload, headers=self.headers, timeout=10) as response:
                if response.status == 200:
                    json_response = await response.json()
                    data = json_response.get("data", [])
                    if data is None:
                        data = []

                    formatted_data = []
                    for item in data:
                        if not item or not isinstance(item, dict):
                            continue
                        symbol_data = item.get("d", [])
                        if symbol_data and len(symbol_data) > 0:
                            formatted_item = {"symbol": item.get("s", "")}
                            for idx, field in enumerate(columns):
                                if idx < len(symbol_data):
                                    formatted_item[field] = symbol_data[idx]
                            formatted_data.append(formatted_item)

                    return {"status": "success", "data": formatted_data}
                else:
                    text = await response.text()
                    return {"status": "failed", "error": f"HTTP {response.status}: {text}"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}

    async def screen_many(self, payloads: List[Dict]) -> List[Dict]:
        """
        Perform multiple screen requests in parallel.

        Each payload should contain: market, filters, columns, and optionally sort_by, sort_order, limit, range_start.
        """
        async with aiohttp.ClientSession() as session:
            tasks = []
            for p in payloads:
                tasks.append(
                    self.screen(
                        session=session,
                        market=p["market"],
                        filters=p["filters"],
                        columns=p["columns"],
                        sort_by=p.get("sort_by"),
                        sort_order=p.get("sort_order", "desc"),
                        limit=p.get("limit", 50),
                        range_start=p.get("range_start", 0),
                    )
                )
            return await asyncio.gather(*tasks)
