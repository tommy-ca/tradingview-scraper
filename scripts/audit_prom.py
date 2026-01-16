from pathlib import Path

import pandas as pd


def audit_prom():
    run_dir = Path("artifacts/summaries/runs/short_all_clean/data")
    phys_path = run_dir / "returns_matrix.parquet"

    if not phys_path.exists():
        print("Data not found")
        return

    df = pd.read_parquet(phys_path)
    if "BINANCE:PROMUSDT" in df.columns:
        ret = df["BINANCE:PROMUSDT"]
        idx = (1 + ret).cumprod()
        print(f"PROMUSDT Return: {idx.iloc[-1] - 1:.2%}")
    else:
        print("PROMUSDT not found")


if __name__ == "__main__":
    audit_prom()
