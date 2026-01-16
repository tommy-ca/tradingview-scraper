from pathlib import Path

import pandas as pd


def audit_ada_short():
    run_dir = Path("artifacts/summaries/runs/short_all_std/data")
    phys_path = run_dir / "returns_matrix.parquet"
    syn_path = run_dir / "synthetic_returns.parquet"

    if not phys_path.exists() or not syn_path.exists():
        print("Data files not found.")
        return

    # Load Data
    phys_df = pd.read_parquet(phys_path)
    syn_df = pd.read_parquet(syn_path)

    symbol = "BINANCE:ADAUSDT"
    atom = f"{symbol}_rating_all_short_SHORT"

    if symbol not in phys_df.columns:
        print(f"{symbol} not in physical returns.")
        return

    # Get Series
    raw_ret = phys_df[symbol]
    # Reconstruct Cumulative Price (Index)
    price_idx = (1 + raw_ret).cumprod()

    print(f"--- {symbol} Physical Analysis ---")
    print(f"Start Date: {raw_ret.index[0]}")
    print(f"End Date:   {raw_ret.index[-1]}")
    print(f"Total Period Return: {price_idx.iloc[-1] - 1:.2%}")

    # Check trend
    if price_idx.iloc[-1] > 1:
        print("TREND: UP (Bullish)")
    else:
        print("TREND: DOWN (Bearish)")

    # Check Max Daily Return
    max_day = raw_ret.max()
    print(f"Max Daily Return: {max_day:.2%}")
    if max_day > 5.0:
        print("WARNING: Data contains extreme outlier spikes (>500%)")

    # Check Synthetic
    if atom in syn_df.columns:
        syn_ret = syn_df[atom]
        syn_idx = (1 + syn_ret).cumprod()
        print(f"\n--- {atom} Synthetic Analysis ---")
        print(f"Total Synthetic Return: {syn_idx.iloc[-1] - 1:.2%}")

        # Validation Logic
        # If Price UP, Short should be DOWN.
        if price_idx.iloc[-1] > 1 and syn_idx.iloc[-1] < 1:
            print("LOGIC CHECK: PASS (Asset Up -> Short Down)")
        elif price_idx.iloc[-1] < 1 and syn_idx.iloc[-1] > 1:
            print("LOGIC CHECK: PASS (Asset Down -> Short Up)")
        else:
            print("LOGIC CHECK: FAIL (Direction mismatch or volatility drag)")

    else:
        print(f"{atom} not found in synthetic matrix.")


if __name__ == "__main__":
    audit_ada_short()
