from unittest.mock import MagicMock

import pandas as pd
import pytest

from tradingview_scraper.pipelines.selection.base import SelectionContext
from tradingview_scraper.pipelines.selection.filters.advanced_trend import AdvancedTrendFilter


@pytest.fixture
def mock_context():
    context = MagicMock(spec=SelectionContext)
    context.candidates = [
        {"symbol": "STRONG_LONG", "direction": "LONG"},
        {"symbol": "WEAK_LONG", "direction": "LONG"},
        {"symbol": "BEAR_LONG", "direction": "LONG"},  # Wrong direction
        {"symbol": "STRONG_SHORT", "direction": "SHORT"},
    ]

    dates = pd.date_range(start="2023-01-01", periods=5)
    data = {}

    # STRONG_LONG: ADX=30, +DI=40, -DI=10 (Strong Up)
    data[("STRONG_LONG", "adx_14")] = [30.0] * 5
    data[("STRONG_LONG", "dmp_14")] = [40.0] * 5
    data[("STRONG_LONG", "dmn_14")] = [10.0] * 5

    # WEAK_LONG: ADX=15 (Weak), +DI=40, -DI=10 (Up but weak)
    data[("WEAK_LONG", "adx_14")] = [15.0] * 5
    data[("WEAK_LONG", "dmp_14")] = [40.0] * 5
    data[("WEAK_LONG", "dmn_14")] = [10.0] * 5

    # BEAR_LONG: ADX=30, +DI=10, -DI=40 (Strong Down)
    data[("BEAR_LONG", "adx_14")] = [30.0] * 5
    data[("BEAR_LONG", "dmp_14")] = [10.0] * 5
    data[("BEAR_LONG", "dmn_14")] = [40.0] * 5

    # STRONG_SHORT: ADX=30, +DI=10, -DI=40 (Strong Down)
    data[("STRONG_SHORT", "adx_14")] = [30.0] * 5
    data[("STRONG_SHORT", "dmp_14")] = [10.0] * 5
    data[("STRONG_SHORT", "dmn_14")] = [40.0] * 5

    df = pd.DataFrame(data, index=dates)
    context.feature_store = df
    return context


def test_adx_regime_long(mock_context):
    f = AdvancedTrendFilter(mode="adx_regime", adx_threshold=20.0)
    ctx, vetoed = f.apply(mock_context)

    assert "STRONG_LONG" not in vetoed
    assert "WEAK_LONG" in vetoed  # Vetoed (ADX < 20)
    assert "BEAR_LONG" in vetoed  # Vetoed (Wrong Direction)


def test_adx_regime_short(mock_context):
    f = AdvancedTrendFilter(mode="adx_regime", adx_threshold=20.0)

    # We need to manually check short behavior on the mock candidates
    # The fixture has STRONG_SHORT which matches logic

    ctx, vetoed = f.apply(mock_context)
    assert "STRONG_SHORT" not in vetoed
