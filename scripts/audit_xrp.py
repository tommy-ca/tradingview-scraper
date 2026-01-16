from pathlib import Path

import pandas as pd


def audit_xrp():
    run_dir = Path("artifacts/summaries/runs/short_all_clean/data")
    phys_path = run_dir / "returns_matrix.parquet"

    if not phys_path.exists():
        print("Data not found")
        return

    df = pd.read_parquet(phys_path)
    if "BINANCE:XRPFDUSD" in df.columns:
        ret = df["BINANCE:XRPFDUSD"]
        idx = (1 + ret).cumprod()
        print(f"XRPFDUSD Return: {idx.iloc[-1] - 1:.2%}")
    else:
        print("XRPFDUSD not found")


if __name__ == "__main__":
    audit_xrp()
