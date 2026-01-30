import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.services.backfill_features import BackfillService


class TestScopedBackfill(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.lakehouse_dir = Path(self.test_dir) / "lakehouse"
        self.lakehouse_dir.mkdir()

        # Create dummy price data for two symbols
        dates = pd.date_range("2024-01-01", periods=100)
        for sym in ["BINANCE_BTCUSDT", "BINANCE_ETHUSDT"]:
            df = pd.DataFrame({"close": np.linspace(100, 110, 100), "high": np.linspace(101, 111, 100), "low": np.linspace(99, 109, 100), "volume": [1000] * 100}, index=dates)
            df.to_parquet(self.lakehouse_dir / f"{sym}_1d.parquet")

        # Create an existing master matrix with only ETH
        self.master_path = self.lakehouse_dir / "features_matrix.parquet"
        existing_data = {("BINANCE:ETHUSDT", "momentum"): pd.Series([0.1] * 100, index=dates)}
        existing_df = pd.DataFrame(existing_data)
        existing_df.columns.names = ["symbol", "feature"]
        existing_df.to_parquet(self.master_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch("scripts.services.backfill_features.get_settings")
    def test_backfill_requires_candidates(self, mock_settings):
        """Verify that backfill fails if no candidates file is provided (Phase 890)."""
        mock_settings.return_value.lakehouse_dir = self.lakehouse_dir
        service = BackfillService(lakehouse_dir=self.lakehouse_dir)

        # We expect it to raise ValueError if candidates_path is None or doesn't exist
        with self.assertRaises(ValueError):
            service.run(candidates_path=None, strict_scope=True)

    @patch("scripts.services.backfill_features.get_settings")
    def test_backfill_uses_metadata_priority(self, mock_settings):
        """Verify that backfill uses features from metadata if available."""
        mock_settings.return_value.lakehouse_dir = self.lakehouse_dir

        # Create a candidates file with metadata features
        candidates_path = Path(self.test_dir) / "candidates.json"
        candidates = [{"symbol": "BINANCE:BTCUSDT", "physical_symbol": "BINANCE:BTCUSDT", "Recommend.All": 0.88, "ADX": 42.0}]
        with open(candidates_path, "w") as f:
            json.dump(candidates, f)

        service = BackfillService(lakehouse_dir=self.lakehouse_dir)

        # Let it run on our dummy parquet
        service.run(candidates_path=candidates_path, output_path=self.master_path, strict_scope=True)

        # Load result
        res_df = pd.read_parquet(self.master_path)

        # BTC should be present
        self.assertIn("BINANCE:BTCUSDT", res_df.columns.get_level_values(0))

        # recommend_all should be 0.88 (from metadata) for the last entry
        # Local calculation would never yield exactly 0.88 on linear dummy data
        self.assertEqual(res_df[("BINANCE:BTCUSDT", "recommend_all")].iloc[-1], 0.88)

        # ETH should still be preserved from setup existing matrix
        self.assertIn("BINANCE:ETHUSDT", res_df.columns.get_level_values(0))


if __name__ == "__main__":
    unittest.main()
