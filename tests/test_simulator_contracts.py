import unittest
import numpy as np
import pandas as pd
import json
from unittest.mock import MagicMock

try:
    import vectorbt

    HAS_VECTORBT = True
except ImportError:
    HAS_VECTORBT = False

from tradingview_scraper.portfolio_engines.backtest_simulators import ReturnsSimulator, VectorBTSimulator, BaseSimulator
from tradingview_scraper.settings import TradingViewScraperSettings, ThreadSafeConfig


class TestSimulatorContracts(unittest.TestCase):
    def setUp(self):
        # Create a basic settings object to avoid file I/O or env var issues
        # We assume the default settings are sufficient for instantiation,
        # but we can override specific fields as needed.
        self.settings = TradingViewScraperSettings()
        # Zero out friction for cleaner directional testing
        self.settings.backtest_slippage = 0.0
        self.settings.backtest_commission = 0.0
        self.token = ThreadSafeConfig.set_active(self.settings)

    def tearDown(self):
        ThreadSafeConfig.reset_active(self.token)

    def test_missing_net_weight(self):
        """Pass a DataFrame without Net_Weight to ReturnsSimulator. Assert ValueError."""
        simulator = ReturnsSimulator()

        # DataFrame without "Net_Weight"
        weights_df = pd.DataFrame(
            {
                "Symbol": ["BTC"],
                "Weight": [0.5],  # Wrong column name
            }
        )

        # Dummy returns
        returns_df = pd.DataFrame({"BTC": [0.01, -0.01]})

        with self.assertRaises(ValueError) as cm:
            simulator.simulate(returns_df, weights_df)

        self.assertIn("Missing Net_Weight", str(cm.exception))

    def test_orphaned_weight(self):
        """Pass a weight for 'SYMBOL_X' but exclude 'SYMBOL_X' from returns matrix. Assert ValueError."""
        simulator = ReturnsSimulator()

        weights_df = pd.DataFrame({"Symbol": ["SYMBOL_X"], "Net_Weight": [0.5]})

        # Returns excluding SYMBOL_X
        returns_df = pd.DataFrame({"SYMBOL_Y": [0.01, 0.02]})

        with self.assertRaises(ValueError) as cm:
            simulator.simulate(returns_df, weights_df)

        self.assertIn("Orphaned weights", str(cm.exception))

    def test_directional_integrity(self):
        """
        Test that shorting a falling asset produces positive returns.
        Setup: Single asset 'BTC'. Price drops from 100 to 90.
        Weights: Net_Weight = -0.5 (Short).
        """
        # Create returns for price dropping from 100 to 90 over 2 steps
        # Step 1: 100 -> 95 (-5%)
        # Step 2: 95 -> 90 (-5.26%)
        returns_data = {"BTC": [-0.05, (90 / 95) - 1.0]}
        returns_df = pd.DataFrame(returns_data)

        weights_df = pd.DataFrame({"Symbol": ["BTC"], "Net_Weight": [-0.5]})

        # 1. Test ReturnsSimulator
        simulator = ReturnsSimulator()
        res = simulator.simulate(returns_df, weights_df)

        daily_returns = res["daily_returns"]
        # Since asset fell and we are short, returns should be positive
        # Check total return or Sharpe
        self.assertGreater(sum(daily_returns), 0.0, "Shorting a falling asset should yield positive returns")

        # 2. Test VectorBTSimulator (if installed)
        if HAS_VECTORBT:
            vbt_sim = VectorBTSimulator()
            # VectorBT simulator might not work if vectorbt is not installed properly,
            # but we wrapped the import. The class itself checks self.vbt is not None.
            # If self.vbt is None, it falls back to ReturnsSimulator, which we already tested.
            # So we strictly check if it's using VBT logic if HAS_VECTORBT is True.

            # Note: VectorBTSimulator.__init__ handles the import error gracefully by setting self.vbt = None
            # So checking HAS_VECTORBT is a good proxy for whether we expect VBT logic.

            # Force vbt instance creation to check if it really loaded
            if vbt_sim.vbt is not None:
                res_vbt = vbt_sim.simulate(returns_df, weights_df)
                daily_returns_vbt = res_vbt["daily_returns"]
                self.assertGreater(sum(daily_returns_vbt), 0.0, "VectorBT: Shorting a falling asset should yield positive returns")

    def test_metric_sanitization(self):
        """
        Mock a simulator output with np.inf, np.nan, np.int64.
        Call _sanitize_metrics.
        Assert output contains only native types and None for nan/inf.
        """
        # Instantiate any simulator to access _sanitize_metrics (defined in BaseSimulator)
        simulator = ReturnsSimulator()

        raw_metrics = {
            "int_val": np.int64(42),
            "float_val": np.float64(3.14),
            "nan_val": np.nan,
            "inf_val": np.inf,
            "neg_inf_val": -np.inf,
            "list_numpy": np.array([1, 2, 3]),
            "nested": {"series": pd.Series([10, 20]), "mixed": [np.int64(1), np.nan]},
        }

        sanitized = simulator._sanitize_metrics(raw_metrics)

        # Assertions
        self.assertIsInstance(sanitized["int_val"], int)
        self.assertNotIsInstance(sanitized["int_val"], np.integer)

        self.assertIsInstance(sanitized["float_val"], float)
        self.assertNotIsInstance(sanitized["float_val"], np.floating)

        self.assertIsNone(sanitized["nan_val"])
        self.assertIsNone(sanitized["inf_val"])
        self.assertIsNone(sanitized["neg_inf_val"])

        self.assertIsInstance(sanitized["list_numpy"], list)
        self.assertIsInstance(sanitized["list_numpy"][0], int)

        self.assertIsInstance(sanitized["nested"]["series"], list)
        self.assertIsInstance(sanitized["nested"]["mixed"], list)
        self.assertIsInstance(sanitized["nested"]["mixed"][0], int)
        self.assertIsNone(sanitized["nested"]["mixed"][1])

        # Verify JSON serialization works without error
        try:
            json_str = json.dumps(sanitized)
        except TypeError as e:
            self.fail(f"Sanitized metrics could not be JSON dumped: {e}")

        self.assertIn("42", json_str)


if __name__ == "__main__":
    unittest.main()
