import json
import sys
from collections import defaultdict
from pathlib import Path


def load_json(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return None


def main():
    export_dir = Path("export")
    files = sorted(list(export_dir.glob("*.json")))

    if not files:
        print("No result files found in export/")
        return

    # Group files by market prefix
    grouped = defaultdict(list)
    for f in files:
        if "futures" in f.name:
            grouped["futures"].append(f)
        elif "cfd" in f.name:
            grouped["cfd"].append(f)
        elif "forex" in f.name:
            grouped["forex"].append(f)
        elif "america" in f.name:
            grouped["america"].append(f)
        else:
            grouped["unknown"].append(f)

    # Process order
    order_map = [("futures", ["Futures L", "Futures S"]), ("cfd", ["CFD L", "CFD S"]), ("forex", ["Forex L", "Forex S"]), ("america", ["US ETFs L", "US ETFs S", "US Stocks L", "US Stocks S"])]

    print(f"{'Market':<15} | {'Symbol':<20} | {'Name':<20} | {'Close':<10} | {'Change%':<8} | {'Rec':<5} | {'ADX':<6} | {'Vol.D':<6}")
    print("-" * 110)

    for market_key, labels in order_map:
        market_files = sorted(grouped.get(market_key, []))
        for i, filepath in enumerate(market_files):
            if i >= len(labels):
                label = f"{market_key} {i + 1}"
            else:
                label = labels[i]

            data = load_json(filepath)
            if not data:
                continue

            if isinstance(data, dict):
                items = data.get("data", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []

            filtered_items = [item for item in items if item.get("passes", {}).get("all", False)]

            # Aggregate by name (deduplicate)
            aggregated = {}
            for item in filtered_items:
                name = item.get("name", "")
                if not name:
                    continue

                # If name exists, keep the one with higher volume
                if name in aggregated:
                    if item.get("volume", 0) > aggregated[name].get("volume", 0):
                        aggregated[name] = item
                else:
                    aggregated[name] = item

            # Sort by volume desc (or original sort) - let's use volume
            sorted_items = sorted(aggregated.values(), key=lambda x: x.get("volume", 0), reverse=True)

            for item in sorted_items:
                symbol = item.get("symbol", "")
                name = item.get("name", "")[:20]  # Truncate
                close = item.get("close", 0)
                change = item.get("change", 0)
                rec = item.get("Recommend.All", 0)
                adx = item.get("ADX", 0)
                vol = item.get("Volatility.D", 0)

                fmt_close = f"{close:.2f}"
                fmt_change = f"{change:+.2f}%"
                fmt_rec = f"{rec:.2f}"
                fmt_adx = f"{adx:.1f}" if adx else "-"
                fmt_vol = f"{vol:.1f}%" if vol else "-"

                print(f"{label:<15} | {symbol:<20} | {name:<20} | {fmt_close:<10} | {fmt_change:<8} | {fmt_rec:<5} | {fmt_adx:<6} | {fmt_vol:<6}")


if __name__ == "__main__":
    main()
