from pathlib import Path

import numpy as np
import pandas as pd


def test_parquet_roundtrip():
    print("Testing MultiIndex Parquet Roundtrip...")

    # 1. Create MultiIndex DataFrame (Time Index x MultiIndex Columns)
    dates = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    iterables = [["binance", "coinbase"], ["BTC", "ETH"]]
    columns = pd.MultiIndex.from_product(iterables, names=["exchange", "symbol"])

    df = pd.DataFrame(np.random.randn(5, 4), index=dates, columns=columns)

    # 2. Save to Parquet
    path = Path("test_multi.parquet")
    df.to_parquet(path)

    # 3. Load back
    loaded = pd.read_parquet(path)

    # 4. Verify
    print(f"Original Columns:\n{df.columns}")
    print(f"Loaded Columns:\n{loaded.columns}")

    pd.testing.assert_frame_equal(df, loaded)
    print("SUCCESS: MultiIndex preserved.")

    # Clean up
    if path.exists():
        path.unlink()


def test_tz_naive_conversion():
    print("\nTesting TZ-Naive -> UTC Parquet Conversion...")

    # 1. Create Naive DataFrame
    dates = pd.date_range("2024-01-01", periods=5, freq="D")  # Naive
    df = pd.DataFrame({"A": range(5)}, index=dates)

    # 2. Apply Migration Logic (from migration script)
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    # 3. Save
    path = Path("test_tz.parquet")
    df.to_parquet(path)

    # 4. Load
    loaded = pd.read_parquet(path)

    print(f"Loaded Index TZ: {loaded.index.tz}")
    assert str(loaded.index.tz) == "UTC" or str(loaded.index.tz) == "datetime.timezone.utc"
    print("SUCCESS: Timezone enforced.")

    if path.exists():
        path.unlink()


if __name__ == "__main__":
    test_parquet_roundtrip()
    test_tz_naive_conversion()
