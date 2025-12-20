import glob
import json
import os

import pandas as pd


def audit_multi_quote():
    # 1. Get latest base universe files for Binance
    spot_base_file = sorted(glob.glob("export/universe_selector_binance_top50_spot_base_*.json"), key=os.path.getmtime, reverse=True)[0]
    perp_base_file = sorted(glob.glob("export/universe_selector_binance_top50_perp_base_*.json"), key=os.path.getmtime, reverse=True)[0]

    # 2. Get latest trend scan files for Binance
    trend_files = glob.glob("export/universe_selector_binance_*_20251220-*.json")
    trend_symbols = set()
    for f in trend_files:
        if "base" in f:
            continue
        with open(f, "r") as j:
            data = json.load(j)
            if isinstance(data, list):
                for item in data:
                    trend_symbols.add(item["symbol"])
            elif isinstance(data, dict) and "data" in data:
                for item in data["data"]:
                    trend_symbols.add(item["symbol"])

    results = []

    def process_base(file_path, ptype):
        with open(file_path, "r") as j:
            data = json.load(j)
            # Standardize to list if it's in the wrapper format
            items = data["data"] if isinstance(data, dict) and "data" in data else data

            for item in items:
                if item.get("alternates") and len(item["alternates"]) > 0:
                    symbol = item["symbol"]
                    alts = item["alternates"]

                    # Check if primary or ANY alternate is in trend symbols
                    in_trend = symbol in trend_symbols or any(alt in trend_symbols for alt in alts)

                    results.append({"Type": ptype, "Primary": symbol, "Alternates": ", ".join(alts), "In Trend": in_trend, "Total VT": item.get("Value.Traded", 0)})

    process_base(spot_base_file, "SPOT")
    process_base(perp_base_file, "PERP")

    df = pd.DataFrame(results)

    print("\n" + "=" * 100)
    print("BINANCE MULTI-QUOTE PAIRS AUDIT")
    print("=" * 100)

    # Filter for those actually in trend for focused research
    trend_focused = df[df["In Trend"] == True].sort_values("Total VT", ascending=False)

    if not trend_focused.empty:
        print("\n>>> Trend-Filtered Candidates (High Priority) <<<")
        print(trend_focused[["Type", "Primary", "Alternates", "Total VT"]].to_string(index=False))

    print("\n>>> All Multi-Quote Pairs <<<")
    print(df.sort_values(["Type", "Total VT"], ascending=[True, False])[["Type", "Primary", "Alternates", "In Trend"]].to_string(index=False))

    # Export mapping for Phase 2
    mapping = {}
    for _, row in df.iterrows():
        mapping[row["Primary"]] = row["Alternates"].split(", ")

    with open("export/multi_quote_mapping.json", "w") as f:
        json.dump(mapping, f, indent=2)
    print("\n[INFO] Mapping exported to export/multi_quote_mapping.json")


if __name__ == "__main__":
    audit_multi_quote()
