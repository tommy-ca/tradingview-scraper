import sys
import types

import pandas as pd

sys.modules.setdefault("pandas_ta_classic", types.SimpleNamespace())

from scripts.services.backfill_features import _process_single_symbol
from tradingview_scraper.utils.technicals import TechnicalRatings


def test_process_single_symbol_writes_utc_index(monkeypatch, tmp_path):
    def _const_series(df: pd.DataFrame, value: float) -> pd.Series:
        return pd.Series(value, index=df.index, dtype=float)

    monkeypatch.setattr(TechnicalRatings, "calculate_recommend_ma_series", staticmethod(lambda df: _const_series(df, 0.2)))
    monkeypatch.setattr(TechnicalRatings, "calculate_recommend_other_series", staticmethod(lambda df: _const_series(df, 0.1)))
    monkeypatch.setattr(TechnicalRatings, "calculate_recommend_all_series", staticmethod(lambda df: _const_series(df, 0.3)))

    lakehouse_dir = tmp_path / "lakehouse"
    lakehouse_dir.mkdir(parents=True)
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True)

    dates = pd.date_range("2024-01-01", periods=5, freq="D")
    ohlcv = pd.DataFrame(
        {
            "open": [1.0, 1.0, 1.0, 1.0, 1.0],
            "high": [1.1, 1.1, 1.1, 1.1, 1.1],
            "low": [0.9, 0.9, 0.9, 0.9, 0.9],
            "close": [1.0, 1.1, 1.2, 1.3, 1.4],
            "volume": [100, 100, 100, 100, 100],
        },
        index=dates,
    )

    (lakehouse_dir / "BINANCE_BTCUSDT_1d.parquet").parent.mkdir(parents=True, exist_ok=True)
    ohlcv.to_parquet(lakehouse_dir / "BINANCE_BTCUSDT_1d.parquet")

    res = _process_single_symbol("BINANCE:BTCUSDT", lakehouse_dir, out_dir)
    assert res is not None
    _, out_path = res

    feat_df = pd.read_parquet(out_path)
    assert isinstance(feat_df.index, pd.DatetimeIndex)
    assert str(feat_df.index.tz) == "UTC"
