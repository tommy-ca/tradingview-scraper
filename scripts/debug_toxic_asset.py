from pathlib import Path

import pandas as pd


def identify_toxic_asset():
    run_dir = Path("artifacts/summaries/runs/short_all_std/data")
    returns_path = run_dir / "synthetic_returns.parquet"

    if not returns_path.exists():
        print("Synthetic returns not found")
        return

    df = pd.read_parquet(returns_path)
    print(f"Loaded {df.shape}")

    # Check min per column
    min_rets = df.min()
    toxic = min_rets[min_rets < -1.0]

    print("\n TOXIC ASSETS (Return < -100%):")
    print(toxic)

    # Detail on worst day
    if not toxic.empty:
        worst_asset = toxic.idxmin()
        worst_day = df[worst_asset].idxmin()
        val = df.loc[worst_day, worst_asset]
        print(f"\nWorst Event: {worst_asset} on {worst_day}: {val:.4f} ({val * 100:.2f}%)")


if __name__ == "__main__":
    identify_toxic_asset()
