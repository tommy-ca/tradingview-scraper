import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from scripts.backtest_engine import BacktestEngine


class TestMultiSimulator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.run_dir = Path(self.test_dir) / "run_sim"
        (self.run_dir / "data").mkdir(parents=True)

        # Create dummy returns
        dates = pd.date_range("2024-01-01", periods=100)
        self.returns = pd.DataFrame({"BTC": [0.01] * 100, "ETH": [-0.01] * 100}, index=dates)
        self.returns.to_parquet(self.run_dir / "data" / "returns_matrix.parquet")

        # Create dummy candidates
        with open(self.run_dir / "data" / "portfolio_candidates.json", "w") as f:
            f.write('[{"symbol": "BTC"}, {"symbol": "ETH"}]')

        self.manifest_path = self.run_dir / "manifest.json"
        with open(self.manifest_path, "w") as f:
            f.write('{"profiles": {"test_prof": {}}}')

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("scripts.backtest_engine.get_settings")
    @patch("scripts.backtest_engine.build_engine")
    @patch("scripts.backtest_engine.build_simulator")
    @patch("scripts.backtest_engine.build_selection_engine")
    @patch("scripts.backtest_engine.AuditLedger")
    def test_run_all_simulators(self, mock_ledger_cls, mock_build_sel, mock_build_sim, mock_build_engine, mock_settings):
        """Verify tournament runs vectorbt, cvxportfolio, and custom simulators."""
        # Setup Mocks
        mock_settings.return_value.prepare_summaries_run_dir.return_value = self.run_dir
        mock_settings.return_value.manifest_path = self.manifest_path
        mock_settings.return_value.profiles = "hrp"
        mock_settings.return_value.engines = "custom"
        # The Tiers
        mock_settings.return_value.backtest_simulators = "vectorbt,cvxportfolio,custom"
        mock_settings.return_value.train_window = 20
        mock_settings.return_value.test_window = 10
        mock_settings.return_value.step_size = 10
        mock_settings.return_value.features.selection_mode = "v4"
        mock_settings.return_value.features.feat_audit_ledger = False
        mock_settings.return_value.profile = "test_prof"
        mock_settings.return_value.top_n = 3
        mock_settings.return_value.threshold = 0.4
        mock_settings.return_value.features.default_shrinkage_intensity = 0.01
        mock_settings.return_value.features.kappa_shrinkage_threshold = 5000.0
        mock_settings.return_value.features.adaptive_fallback_profile = "erc"
        mock_settings.return_value.benchmark_symbols = []

        # Mock Ledger
        mock_ledger = MagicMock()
        mock_ledger_cls.return_value = mock_ledger

        # Mock Engine
        mock_engine_instance = MagicMock()
        mock_engine_instance.optimize.return_value.weights = pd.DataFrame({"Symbol": ["BTC", "ETH"], "Weight": [0.5, 0.5], "Net_Weight": [0.5, 0.5]})
        mock_build_engine.return_value = mock_engine_instance

        # Mock Selection
        mock_sel = MagicMock()
        mock_sel.select.return_value.winners = [{"symbol": "BTC"}, {"symbol": "ETH"}]
        mock_sel.select.return_value.metrics = {}
        mock_sel.select.return_value.relaxation_stage = 1
        mock_sel.select.return_value.audit_clusters = {}
        mock_build_sel.return_value = mock_sel

        # Mock Simulators
        sim_mock = MagicMock()
        sim_mock.simulate.return_value = {"metrics": {"sharpe": 1.0, "daily_returns": pd.Series([0.01] * 10, index=pd.date_range("2024-01-01", periods=10))}}
        mock_build_sim.return_value = sim_mock

        # Initialize Engine
        engine = BacktestEngine()
        engine.settings = mock_settings.return_value
        engine.load_data(self.run_dir)

        # Run
        result = engine.run_tournament(mode="research", run_dir=self.run_dir)

        # Assertions
        # Should have run 3 simulators for each engine/profile iteration.
        # Window count = (100 - 20 - 10) / 10 + 1 = 8 windows?
        # Actually it's windows: [20, 30, 40, 50, 60, 70]?
        # range(20, 100-10, 10) -> 20, 30, 40, 50, 60, 70, 80. (7 windows)

        # Each window runs 1 engine * 1 profile * 3 simulators = 3 simulations.
        # Total results should be 7 * 3 = 21.
        self.assertTrue(len(result["results"]) > 0)

        sim_names_run = set(r["simulator"] for r in result["results"])
        self.assertIn("vectorbt", sim_names_run)
        self.assertIn("cvxportfolio", sim_names_run)
        self.assertIn("custom", sim_names_run)
        self.assertNotIn("nautilus", sim_names_run)


if __name__ == "__main__":
    unittest.main()
