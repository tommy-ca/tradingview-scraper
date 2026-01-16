from pathlib import Path

import pandas as pd


def inspect_raw_prices():
    # Load from the std run where data was prepped
    run_dir = Path("artifacts/summaries/runs/short_all_std/data")
    path = run_dir / "returns_matrix.parquet"

    if not path.exists():
        print("Path not found")
        return

    df = pd.read_parquet(path)
    # Check ADA around 2026-01-01
    target_date = "2026-01-01"

    try:
        # Get slice
        subset = df.loc["2025-12-25":"2026-01-05", ["BINANCE:ADAUSDT"]]
        print(subset)
    except Exception as e:
        print(e)
        print(df.index[-5:])  # Show last 5 dates


if __name__ == "__main__":
    inspect_raw_prices()
