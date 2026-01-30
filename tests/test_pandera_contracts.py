import unittest
import pandas as pd
import numpy as np
import pandera as pa
from tradingview_scraper.pipelines.contracts import (
    ReturnsSchema,
    WeightsSchema,
    InferenceSchema,
    SyntheticReturnsSchema,
)


class TestPanderaContracts(unittest.TestCase):
    def test_returns_contract_validation(self):
        """Verify that malformed returns are rejected with descriptive errors."""
        # Clean data
        df_ok = pd.DataFrame({"BTC": [0.01, -0.02, 0.03]}, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))

        ReturnsSchema.validate(df_ok)

        # Toxic data (> 100% daily)
        df_toxic = pd.DataFrame({"BTC": [0.01, 6.0, 0.03]}, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))

        with self.assertRaises(pa.errors.SchemaError):
            ReturnsSchema.validate(df_toxic)

    def test_inference_schema(self):
        """Verify L2 Inference Schema enforces [0, 1] bounds for alpha scores."""
        # Clean data
        df_ok = pd.DataFrame(
            {
                "alpha_score": [0.5, 0.9, 0.1],
                "momentum_prob": [0.6, 0.8, 0.2],
            },
            index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
        )
        InferenceSchema.validate(df_ok)

        # Invalid alpha score (> 1.0)
        df_bad = pd.DataFrame(
            {"alpha_score": [1.5]},
            index=pd.to_datetime(["2024-01-01"]),
        )
        with self.assertRaises(pa.errors.SchemaError):
            InferenceSchema.validate(df_bad)

    def test_synthetic_returns_schema(self):
        """Verify L3 Synthetic Schema ensures returns are within bounds."""
        # Clean data
        df_ok = pd.DataFrame(
            {"ATOM_1": [0.05, -0.05], "ATOM_2": [0.02, 0.01]},
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        )
        SyntheticReturnsSchema.validate(df_ok)

        # Toxic synthetic return (e.g., from a leveraged short squeeze)
        df_toxic = pd.DataFrame(
            {"ATOM_1": [-2.0]},  # -200% loss
            index=pd.to_datetime(["2024-01-01"]),
        )
        # Note: Depending on logic, shorts might be inverted.
        # But contract says |r| <= 1.0.
        with self.assertRaises(pa.errors.SchemaError):
            SyntheticReturnsSchema.validate(df_toxic)

    def test_weights_sum_contract(self):
        """Verify that WeightsSchema detects weight leakage."""
        df_leak = pd.DataFrame(
            {
                "Symbol": ["A", "B"],
                "Weight": [0.6, 0.6],  # Sum = 1.2
            }
        )

        with self.assertRaises(pa.errors.SchemaError):
            WeightsSchema.validate(df_leak)


if __name__ == "__main__":
    unittest.main()
