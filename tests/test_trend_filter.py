from unittest.mock import MagicMock

import pandas as pd
import pytest

from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.filters.trend import TrendRegimeFilter


@pytest.fixture
def mock_context():
    context = MagicMock(spec=SelectionContext)
    context.params = {"trend_lookback": 5}
    context.candidates = [
        {"symbol": "BTC", "direction": "LONG"},
        {"symbol": "ETH", "direction": "SHORT"},
        {"symbol": "SOL", "direction": "LONG"},
    ]
    # Mock Feature Store
    # We need Close, SMA200, VWMA20
    # Format: MultiIndex (symbol, feature)

    dates = pd.date_range(start="2023-01-01", periods=10)
    data = {}

    # BTC: Bull Trend (Close > SMA200), Golden Cross (VWMA crosses above SMA)
    # Day 8: VWMA < SMA (98 < 100)
    # Day 9: VWMA > SMA (102 > 100) -> Cross!
    data[("BTC", "close")] = [110.0] * 10
    data[("BTC", "sma_200")] = [100.0] * 10
    data[("BTC", "vwma_20")] = [90, 91, 92, 93, 94, 95, 96, 98, 102, 105]

    # ETH: Bear Trend (Close < SMA200), Death Cross (VWMA crosses below SMA)
    data[("ETH", "close")] = [90.0] * 10
    data[("ETH", "sma_200")] = [100.0] * 10
    data[("ETH", "vwma_20")] = [110, 108, 106, 104, 102, 101, 100.5, 100.1, 99.0, 95.0]

    # SOL: Bull Trend, No Cross (Always above)
    data[("SOL", "close")] = [150.0] * 10
    data[("SOL", "sma_200")] = [100.0] * 10
    data[("SOL", "vwma_20")] = [120.0] * 10

    df = pd.DataFrame(data, index=dates)
    context.feature_store = df
    return context


def test_trend_regime_filter_long(mock_context):
    f = TrendRegimeFilter(strict_regime=True, strict_signal=True)

    # Test BTC (Long)
    # Should PASS: Close(110) > SMA(100) AND Cross in last 5 days
    # Test SOL (Long)
    # Should FAIL Signal: No cross in last 5 days

    ctx, vetoed = f.apply(mock_context)

    assert "BTC" not in vetoed
    assert "SOL" in vetoed  # Vetoed due to lack of signal


def test_trend_regime_filter_short(mock_context):
    f = TrendRegimeFilter(strict_regime=True, strict_signal=True)

    # Test ETH (Short)
    # Should PASS: Close(90) < SMA(100) AND Death Cross in last 5 days

    ctx, vetoed = f.apply(mock_context)
    assert "ETH" not in vetoed


def test_trend_regime_only(mock_context):
    # Test with signal check disabled
    f = TrendRegimeFilter(strict_regime=True, strict_signal=False)

    ctx, vetoed = f.apply(mock_context)

    assert "BTC" not in vetoed  # Bull Regime
    assert "SOL" not in vetoed  # Bull Regime (Signal ignored)
    assert "ETH" not in vetoed  # Bear Regime (matches direction=SHORT)
