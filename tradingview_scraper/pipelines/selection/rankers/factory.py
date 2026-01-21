from typing import Any, Dict, Optional

from tradingview_scraper.pipelines.selection.rankers.base import BaseRanker
from tradingview_scraper.pipelines.selection.rankers.mps import MPSRanker
from tradingview_scraper.pipelines.selection.rankers.regime import StrategyRegimeRanker
from tradingview_scraper.pipelines.selection.rankers.signal import SignalRanker


class RankerFactory:
    """
    Factory for creating Selection Ranker instances based on configuration.
    """

    @staticmethod
    def get_ranker(method: str, config: Optional[Dict[str, Any]] = None) -> BaseRanker:
        config = config or {}

        if method == "mps" or method == "alpha_score":
            return MPSRanker()

        if method == "signal":
            signal_name = config.get("signal", "recommend_ma")
            return SignalRanker(signal_name=signal_name)

        if method == "regime":
            strategy = config.get("strategy", "trend_following")
            return StrategyRegimeRanker(strategy=strategy)

        # Default fallback
        return MPSRanker()
