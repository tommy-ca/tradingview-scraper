import logging
from typing import cast

import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Detects market volatility regimes to inform portfolio optimization strategy.
    """

    def __init__(self, crisis_threshold: float = 2.5):
        """
        Args:
            crisis_threshold: Multiplier above mean volatility to trigger CRISIS regime.
        """
        self.crisis_threshold = crisis_threshold

    def detect_regime(self, returns: pd.DataFrame) -> str:
        """
        Analyzes the return matrix and classifies the current regime.

        Returns:
            str: 'QUIET', 'NORMAL', or 'CRISIS'
        """
        if returns.empty or len(returns) < 2:
            return "NORMAL"

        # 1. Calculate Rolling Volatility (using cross-sectional average for global proxy)
        # mean(axis=1) on a DataFrame returns a Series
        mean_returns = returns.mean(axis=1)
        if not isinstance(mean_returns, pd.Series) or len(mean_returns) < 2:
            return "NORMAL"

        market_returns = cast(pd.Series, mean_returns)

        # Use a short lookback for 'current' vol
        current_vol = float(market_returns.tail(5).std())
        # Use a longer lookback for 'baseline' vol
        baseline_vol = float(market_returns.std())

        if pd.isna(current_vol) or pd.isna(baseline_vol) or baseline_vol == 0:
            return "NORMAL"

        vol_ratio = current_vol / baseline_vol

        logger.info(f"Regime Detection - Current Vol: {current_vol:.4f}, Baseline: {baseline_vol:.4f}, Ratio: {vol_ratio:.2f}")

        if vol_ratio >= self.crisis_threshold:
            return "CRISIS"
        elif vol_ratio < 0.5:
            return "QUIET"
        else:
            return "NORMAL"
