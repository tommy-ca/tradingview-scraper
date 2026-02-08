import sys
import types

import pandas as pd

# Provide stub for optional dependency required by backfill_features imports
sys.modules.setdefault("pandas_ta_classic", types.SimpleNamespace())

from scripts.services import backfill_features
from scripts.services.backfill_features import BackfillService


def test_backfill_merge_block_assignment(monkeypatch, tmp_path):
    svc = BackfillService(lakehouse_dir=tmp_path)

    # Existing matrix with one symbol/feature
    existing = pd.DataFrame({("A", "foo"): [1.0, 2.0]}, index=pd.to_datetime(["2024-01-01", "2024-01-02"]))
    out_p = tmp_path / "features_matrix.parquet"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    existing.to_parquet(out_p)

    # Provide lakehouse OHLCV to satisfy worker symbol discovery
    lake_file = tmp_path / "BINANCE_A_1d.parquet"
    ohlcv = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "close": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "volume": [1000, 1100],
        }
    )
    ohlcv.to_parquet(lake_file, index=False)

    # Patch settings to point to temp lakehouse and disable strict scope
    monkeypatch.setattr(svc, "lakehouse_dir", tmp_path)

    # Provide new features
    new_df = pd.DataFrame({("A", "foo"): [3.0], ("A", "bar"): [4.0]}, index=pd.to_datetime(["2024-01-02"]))

    def fake_worker(sym, lakehouse_dir, meta=None):
        return new_df.to_dict(orient="series")

    # Inline executor to avoid process spawning and ensure fake_worker usage
    class DummyFuture:
        def __init__(self, result_func):
            self._result = result_func

        def result(self):
            return self._result()

    class DummyExecutor:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def submit(self, fn, *args, **kwargs):
            return DummyFuture(lambda: fn(*args, **kwargs))

    monkeypatch.setattr(backfill_features, "_backfill_worker", fake_worker)
    monkeypatch.setattr(backfill_features, "ProcessPoolExecutor", DummyExecutor)
    monkeypatch.setattr(backfill_features, "as_completed", lambda futures: futures)

    # Run with prepared symbols
    svc.run(candidates_path=None, output_path=out_p, strict_scope=False)

    final = pd.read_parquet(out_p)
    # Expect merged index and both columns, with new overriding existing on overlap
    assert ("A", "foo") in final.columns
    assert ("A", "bar") in final.columns
    assert final.loc[pd.Timestamp("2024-01-02"), ("A", "foo")] == 3.0
