import unittest
import pandas as pd
import numpy as np
import pandera as pa
from tradingview_scraper.pipelines.contracts import ReturnsSchema, AuditSchema, ReturnsMatrixSchema, WeightsSchema


class TestPanderaContracts(unittest.TestCase):
    def test_returns_matrix_contract_validation(self):
        """Verify that malformed returns matrices (Wide) are rejected with descriptive errors."""
        # Clean data
        df_ok = pd.DataFrame({"BTC": [0.01, -0.02, 0.03]}, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))

        ReturnsMatrixSchema.validate(df_ok)

        # Toxic data (> 100% daily)
        df_toxic = pd.DataFrame({"BTC": [0.01, 6.0, 0.03]}, index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]))

        with self.assertRaises(pa.errors.SchemaError):
            ReturnsMatrixSchema.validate(df_toxic)

    def test_returns_schema_tier1(self):
        """Verify Tier 1 Structural Schema (Long Format)."""
        # Clean data
        df_ok = pd.DataFrame({"date": pd.to_datetime(["2024-01-01", "2024-01-02"]), "symbol": ["BTC", "BTC"], "returns": [0.01, -0.02]})

        ReturnsSchema.validate(df_ok)

        # Missing column
        df_bad = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "returns": [0.01]})
        with self.assertRaises(pa.errors.SchemaError):
            ReturnsSchema.validate(df_bad)

    def test_audit_schema_tier2(self):
        """Verify Tier 2 Semantic Schema (Audit)."""
        # 1. Valid Range Check
        df_toxic = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-01"]),
                "symbol": ["BTC"],
                "returns": [15.0],  # > 10.0 limit
            }
        )
        with self.assertRaises(pa.errors.SchemaError):
            AuditSchema.validate(df_toxic)

        # 2. No Weekend Padding (TradFi)
        # Create a weekend date
        weekend_date = pd.Timestamp("2024-01-06")  # Saturday

        # TradFi with 0.0 on weekend -> Should Fail
        df_padding_tradfi = pd.DataFrame(
            {
                "date": [weekend_date],
                "symbol": ["AAPL"],  # TradFi
                "returns": [0.0],
            }
        )

        with self.assertRaises(pa.errors.SchemaError) as cm:
            AuditSchema.validate(df_padding_tradfi)
        self.assertIn("TradFi assets detected with zero-filled weekend returns", str(cm.exception))

        # Crypto with 0.0 on weekend -> Should Pass
        df_padding_crypto = pd.DataFrame(
            {
                "date": [weekend_date],
                "symbol": ["BINANCE:BTCUSDT"],  # Crypto
                "returns": [0.0],
            }
        )
        AuditSchema.validate(df_padding_crypto)

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
