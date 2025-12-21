import logging

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
        if returns.empty:
            return "NORMAL"

        # 1. Calculate Rolling Volatility (using cross-sectional average for global proxy)
        market_returns = returns.mean(axis=1)
        # Use a short lookback for 'current' vol
        current_vol = market_returns.tail(5).std()
        # Use a longer lookback for 'baseline' vol
        baseline_vol = market_returns.std()

        if baseline_vol == 0:
            return "QUIET"

        vol_ratio = current_vol / baseline_vol

        logger.info(f"Regime Detection - Current Vol: {current_vol:.4f}, Baseline: {baseline_vol:.4f}, Ratio: {vol_ratio:.2f}")

        if vol_ratio >= self.crisis_threshold:
            return "CRISIS"
        elif vol_ratio < 0.5:
            return "QUIET"
        else:
            return "NORMAL"
