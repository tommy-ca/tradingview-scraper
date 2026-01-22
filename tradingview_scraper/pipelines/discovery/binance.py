import logging
from typing import Any, Dict, List

import ccxt

from tradingview_scraper.pipelines.discovery.base import (
    BaseDiscoveryScanner,
    CandidateMetadata,
)

logger = logging.getLogger(__name__)


class BinanceDiscoveryScanner(BaseDiscoveryScanner):
    """
    Discovery scanner that sources assets from Binance (Spot/Perp) via CCXT.
    """

    @property
    def name(self) -> str:
        return "binance"

    def discover(self, params: Dict[str, Any]) -> List[CandidateMetadata]:
        """
        Executes discovery on Binance and maps results to CandidateMetadata.

        Args:
            params:
                - asset_type: "spot" (default) or "swap" (futures)
                - quote: "USDT" (default)
                - min_volume: Minimum 24h volume filter
        """
        asset_type = params.get("asset_type", "spot")
        quote = params.get("quote", "USDT")
        min_volume = float(params.get("min_volume", 0))

        logger.info(f"Executing Binance discovery (type={asset_type}, quote={quote})...")

        try:
            exchange = ccxt.binance({"enableRateLimit": True, "options": {"defaultType": asset_type}})

            markets = exchange.load_markets()
            tickers = exchange.fetch_tickers()

            candidates = []
            for symbol, market in markets.items():
                # Filter by active status and quote currency
                if not market.get("active"):
                    continue
                if market.get("quote") != quote:
                    continue

                # Filter by volume if ticker available
                ticker = tickers.get(symbol, {})
                volume_raw = ticker.get("quoteVolume", 0)
                volume = float(volume_raw) if volume_raw is not None else 0.0

                if volume < min_volume:
                    continue

                # Map to CandidateMetadata
                # CCXT symbol is typically BTC/USDT.
                # Downstream expects BINANCE:BTCUSDT
                base = market.get("base")
                quote_curr = market.get("quote")
                clean_symbol = f"{base}{quote_curr}"

                identity = f"BINANCE:{clean_symbol}"

                cand = CandidateMetadata(
                    symbol=identity,
                    exchange="BINANCE",
                    asset_type="spot" if asset_type == "spot" else "perp",
                    volume_24h=volume,
                    metadata={"ccxt_symbol": symbol, "market_type": market.get("type"), "last_price": ticker.get("last"), "change_24h": ticker.get("percentage")},
                )
                candidates.append(cand)

            logger.info(f"Discovered {len(candidates)} candidates on Binance.")
            return candidates

        except Exception as e:
            logger.error(f"Binance discovery failed: {e}", exc_info=True)
            return []
