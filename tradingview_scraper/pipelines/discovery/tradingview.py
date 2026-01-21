import logging
from typing import Any, Dict, List

from tradingview_scraper.futures_universe_selector import (
    FuturesUniverseSelector,
    SelectorConfig,
    load_config,
)
from tradingview_scraper.pipelines.discovery.base import (
    BaseDiscoveryScanner,
    CandidateMetadata,
)

logger = logging.getLogger(__name__)


class TradingViewDiscoveryScanner(BaseDiscoveryScanner):
    """
    Discovery scanner that leverages the TradingView Screener API
    via FuturesUniverseSelector.
    """

    @property
    def name(self) -> str:
        return "tradingview"

    def discover(self, params: Dict[str, Any]) -> List[CandidateMetadata]:
        """
        Executes a TradingView screen and maps results to CandidateMetadata.
        """
        # 1. Load config (handles inheritance if base_preset is in params)
        try:
            # If params is a string, it's a path to a config file
            # If params is a dict, it's the config itself
            cfg = load_config(params)
            selector = FuturesUniverseSelector(cfg)

            # 2. Run the selector
            # Note: run() handles screening and post-filtering
            result = selector.run()

            if result.get("status") not in ["success", "partial_success"]:
                logger.error(f"TradingView screen failed: {result.get('errors')}")
                return []

            # 3. Map to CandidateMetadata
            candidates = []
            for row in result.get("data", []):
                symbol = row.get("symbol")
                if not symbol:
                    continue

                # Extract exchange from symbol if not present in row
                exchange = row.get("exchange")
                if not exchange and ":" in symbol:
                    exchange = symbol.split(":")[0]
                exchange = exchange or "UNKNOWN"

                # Determine asset type
                # (This is a bit heuristic, could be improved)
                asset_type = row.get("type", "spot")
                if symbol.endswith(".P"):
                    asset_type = "perp"

                cand = CandidateMetadata(
                    symbol=symbol,
                    exchange=exchange,
                    asset_type=asset_type,
                    market_cap_rank=row.get("market_cap_rank"),
                    volume_24h=row.get("volume"),
                    sector=row.get("sector"),
                    industry=row.get("industry"),
                    metadata=row,
                )
                candidates.append(cand)

            return candidates

        except Exception as e:
            logger.error(f"TradingView discovery failed: {e}", exc_info=True)
            return []
