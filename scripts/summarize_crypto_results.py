import glob
import json
import os

import pandas as pd


def summarize_results():
    files = sorted(glob.glob("export/universe_selector_*_base_*.json"), key=os.path.getmtime, reverse=True)[:8]

    matrix_summary = []

    print("\n" + "=" * 120)
    print("DETAILED CRYPTO BASE UNIVERSE SUMMARY (With Alternates)")
    print("=" * 120)

    for f in files:
        with open(f, "r") as j:
            rows = json.load(j)

            basename = os.path.basename(str(f))
            parts = basename.split("_")
            if len(parts) >= 5:
                exchange = parts[2].upper()
                ptype = parts[4].upper()
            else:
                continue

            df = pd.DataFrame(rows)
            if df.empty:
                continue

            if "alternates" not in df.columns:
                df["alternates"] = [[] for _ in range(len(df))]

            total_bases = len(df)
            bases_with_alts = df["alternates"].apply(lambda x: len(x) if isinstance(x, list) else 0).gt(0).sum()
            total_alts = df["alternates"].apply(lambda x: len(x) if isinstance(x, list) else 0).sum()

            matrix_summary.append({"Exchange": exchange, "Type": ptype, "Unique Bases": total_bases, "Bases w/ Alts": bases_with_alts, "Total Alts": total_alts})

            # Show Top 10 for this specific universe
            print(f"\n>>> {exchange} {ptype} (Top 10 by Summed VT) <<<")

            display_cols = ["symbol", "Value.Traded"]
            if "alternates" in df.columns:
                # Create a readable 'alternatives' string
                df["alts_str"] = df["alternates"].apply(lambda x: ", ".join(x) if isinstance(x, list) and x else "-")
                display_cols.append("alts_str")

            top_10 = df.head(10)[display_cols].copy()
            top_10.columns = ["Symbol", "Total VT", "Alternatives"]
            top_10["Total VT"] = top_10["Total VT"].apply(lambda x: f"${x / 1e6:.1f}M")

            print(top_10.to_string(index=False))
            print("-" * 80)

    # Final Matrix Table
    print("\n" + "=" * 100)
    print("AGGREGATION MATRIX OVERVIEW")
    print("=" * 100)
    df_matrix = pd.DataFrame(matrix_summary)
    print(df_matrix.to_string(index=False))
    print("=" * 100)


if __name__ == "__main__":
    summarize_results()
