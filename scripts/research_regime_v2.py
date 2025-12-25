import logging
import os
from typing import cast

import pandas as pd

from tradingview_scraper.regime import MarketRegimeDetector

logging.basicConfig(level=logging.INFO)


def research_regime():
    returns_path = "data/lakehouse/portfolio_returns.pkl"
    if not os.path.exists(returns_path):
        print("Returns matrix missing.")
        return

    returns = cast(pd.DataFrame, pd.read_pickle(returns_path))
    detector = MarketRegimeDetector()

    # Test full series
    regime = detector.detect_regime(returns)
    print(f"\nFinal Identified Regime: {regime}")

    # Test sub-slices to see if it changes
    # Recent 20 days
    recent = returns.tail(20)
    print(f"Recent 20d Regime: {detector.detect_regime(recent)}")

    # Middle slice
    if len(returns) > 100:
        middle = returns.iloc[20:80]
        print(f"Middle 60d Regime: {detector.detect_regime(middle)}")


if __name__ == "__main__":
    research_regime()
