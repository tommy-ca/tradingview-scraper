import json
import sys
import types

import numpy as np
import pandas as pd
import pytest

# backfill_features imports pandas_ta_classic; stub it for test isolation.
sys.modules.setdefault("pandas_ta_classic", types.SimpleNamespace())

from scripts.services.backfill_features import BackfillService
from tradingview_scraper.utils.technicals import TechnicalRatings


@pytest.fixture
def mock_workspace(tmp_path):
    """Creates a mock workspace with candidates and lakehouse data."""
    # Setup directories
    lakehouse_dir = tmp_path / "data" / "lakehouse"
    lakehouse_dir.mkdir(parents=True)

    # Create dummy OHLCV data for 2 symbols
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")

    # Symbol A: Uptrend (Should have high rating)
    price_a = np.linspace(100, 200, 100)
    df_a = pd.DataFrame({"open": price_a, "high": price_a + 1, "low": price_a - 1, "close": price_a, "volume": 1000}, index=dates)
    df_a.to_parquet(lakehouse_dir / "SYMBOL_A_1d.parquet")

    # Symbol B: Downtrend (Should have low rating)
    price_b = np.linspace(200, 100, 100)
    df_b = pd.DataFrame({"open": price_b, "high": price_b + 1, "low": price_b - 1, "close": price_b, "volume": 1000}, index=dates)
    df_b.to_parquet(lakehouse_dir / "SYMBOL_B_1d.parquet")

    # Create candidates.json
    candidates = [{"symbol": "SYMBOL:A", "description": "Test A"}, {"symbol": "SYMBOL:B", "description": "Test B"}]
    candidates_path = tmp_path / "candidates.json"
    with open(candidates_path, "w") as f:
        json.dump(candidates, f)

    return {"root": tmp_path, "lakehouse": lakehouse_dir, "candidates": candidates_path, "output": tmp_path / "features_matrix.parquet"}


def test_backfill_execution(mock_workspace, monkeypatch):
    """Test that the backfill service generates the output matrix."""

    def _const_series(df: pd.DataFrame, value: float) -> pd.Series:
        return pd.Series(value, index=df.index, dtype=float)

    # Keep the backfill test deterministic and independent of pandas_ta_classic.
    monkeypatch.setattr(TechnicalRatings, "calculate_recommend_ma_series", staticmethod(lambda df: _const_series(df, 0.2)))
    monkeypatch.setattr(TechnicalRatings, "calculate_recommend_other_series", staticmethod(lambda df: _const_series(df, 0.1)))
    monkeypatch.setattr(TechnicalRatings, "calculate_recommend_all_series", staticmethod(lambda df: _const_series(df, 0.3)))

    service = BackfillService(lakehouse_dir=mock_workspace["lakehouse"])

    service.run(candidates_path=mock_workspace["candidates"], output_path=mock_workspace["output"])

    assert mock_workspace["output"].exists()

    df = pd.read_parquet(mock_workspace["output"])
    assert not df.empty

    assert isinstance(df.index, pd.DatetimeIndex)
    assert str(df.index.tz) == "UTC"
    # Columns are MultiIndex (symbol, feature)
    # Check if symbol level exists
    assert "SYMBOL:A" in df.columns.get_level_values(0)
    assert "SYMBOL:B" in df.columns.get_level_values(0)

    # Verify join alignment with a UTC returns matrix (timezone mismatch would empty the join).
    dates_utc = pd.date_range(start="2023-01-01", periods=100, freq="D", tz="UTC")
    returns = pd.DataFrame({"returns": np.linspace(0.0, 0.01, len(dates_utc))}, index=dates_utc)
    joined = returns.join(df[("SYMBOL:A", "recommend_all")].rename("recommend_all"), how="inner")
    assert len(joined) == len(returns)

    # Verify range
    assert df.max().max() <= 1.0
    assert df.min().min() >= -1.0
