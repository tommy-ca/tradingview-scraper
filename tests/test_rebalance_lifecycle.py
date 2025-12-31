import numpy as np
import pandas as pd
import pytest
from tradingview_scraper.portfolio_engines.backtest_simulators import CvxPortfolioSimulator
from tradingview_scraper.settings import get_settings


def test_rebalance_with_universe_shift():
    """Verify that backtest simulators handle shifts in asset availability."""
    simulator = CvxPortfolioSimulator()
    if simulator.cvp is None:
        pytest.skip("cvxportfolio not installed")

    dates = pd.date_range("2023-01-01", periods=10, tz="UTC")

    # Setup returns: Asset A exists all time, Asset B vanishes, Asset C appears
    # Window 1: A and B
    # Window 2: A and C
    rets = pd.DataFrame(np.random.normal(0.001, 0.01, (10, 3)), index=dates, columns=["A", "B", "C"])  # type: ignore

    # Weight state 1 (A=0.5, B=0.5)
    w1 = pd.DataFrame([{"Symbol": "A", "Weight": 0.5}, {"Symbol": "B", "Weight": 0.5}])

    # Weight state 2 (A=0.5, C=0.5) - B was sold, C was bought
    w2 = pd.DataFrame([{"Symbol": "A", "Weight": 0.5}, {"Symbol": "C", "Weight": 0.5}])

    # Simulating window 1
    perf1 = simulator.simulate(rets.iloc[:5], w1)
    assert perf1["total_return"] is not None

    # Simulating window 2 (Transition)
    perf2 = simulator.simulate(rets.iloc[5:], w2)
    assert perf2["total_return"] != 0

    # The key is that the simulator didn't crash when B was in weights but not in test_data
    # (though here B is in rets, but we check if it handles available symbols correctly)


def test_returns_simulator_normalization():
    """Verify that ReturnsSimulator re-normalizes weights when assets are missing."""
    from tradingview_scraper.portfolio_engines.backtest_simulators import ReturnsSimulator

    sim = ReturnsSimulator()

    dates = pd.date_range("2023-01-01", periods=5)
    test_data = pd.DataFrame(np.random.randn(5, 2), index=dates, columns=["A", "B"])  # type: ignore

    # Weight for A, B, and C (C is missing)
    weights = pd.DataFrame([{"Symbol": "A", "Weight": 0.4}, {"Symbol": "B", "Weight": 0.4}, {"Symbol": "C", "Weight": 0.2}])

    perf = sim.simulate(test_data, weights)

    # Effective weights should be A=0.5, B=0.5
    # daily_return = 0.5 * retA + 0.5 * retB
    expected = test_data["A"] * 0.5 + test_data["B"] * 0.5
    pd.testing.assert_series_equal(perf["daily_returns"], expected, check_names=False)
