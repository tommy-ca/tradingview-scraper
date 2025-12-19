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


def normalize_name(name):
    """Normalize asset name by removing common suffixes."""
    # Suffixes to remove
    suffixes = [".P", ".I", ".a", ".s", "_mini", "1!", "Z2025", "F2026", "G2025", "H2025", ".ONE", ".SML", ".PRO.OTMS", ".TV"]

    # Simple strip of known suffixes
    # Note: Some suffixes might be part of the symbol (e.g. 'P' in stock ticker),
    # but for Forex/CFD 'AUDNOK.P', it's safe.
    # For Futures 'SAILZ2025' -> 'SAIL'. 'SAIL1!' -> 'SAIL'.
    # We need to be careful not to over-normalize stocks if they have these chars.
    # But usually suffixes are after a dot or specific futures codes.

    # Heuristic: if dot exists, split by dot.
    if "." in name:
        base = name.split(".")[0]
        # Check if suffix is in our ignore list or looks like one
        # Actually, for Forex 'AUDNOK.P', base is 'AUDNOK'.
        return base

    # For Futures like 'SAIL1!', 'SAILZ2025'
    if name.endswith("1!"):
        return name[:-2]

    # Removing 'Z2025' etc is harder without regex, but we can try common ones if they appear at end.
    # Since specific futures contracts (Z2025) are distinct from continuous (1!), maybe we WANT to keep them separate?
    # User said "normalized name, so we have clear understanding of global candidates".
    # Seeing 'SAIL' is better than 'SAILZ2025' and 'SAIL1!' separate.
    # But strictly speaking, they are different instruments.
    # However, for "trend opportunity", knowing SAIL is trending is the key.

    return name


def main():
    export_dir = Path("export")
    files = sorted(list(export_dir.glob("*.json")))

    if not files:
        print("No result files found in export/")
        return

    # Group files by market prefix
    grouped = defaultdict(list)
    for f in files:
        if "futures_metals" in f.name:
            grouped["metals"].append(f)
        elif "futures" in f.name:
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
    order_map = [
        ("futures", ["Futures L", "Futures S"]),
        ("metals", ["Metals L", "Metals S"]),
        ("cfd", ["CFD L", "CFD S"]),
        ("forex", ["Forex L", "Forex S"]),
        ("america", ["US ETFs L", "US ETFs S", "US Stocks L", "US Stocks S"]),
    ]

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

            # Aggregate by normalized name (deduplicate)
            aggregated = {}
            for item in filtered_items:
                raw_name = item.get("name", "")
                if not raw_name:
                    continue

                norm_name = normalize_name(raw_name)

                # If name exists, keep the one with higher volume
                if norm_name in aggregated:
                    if item.get("volume", 0) > aggregated[norm_name].get("volume", 0):
                        aggregated[norm_name] = item
                else:
                    aggregated[norm_name] = item

            # Sort by volume desc
            sorted_items = sorted(aggregated.values(), key=lambda x: x.get("volume", 0), reverse=True)

            for item in sorted_items:
                symbol = item.get("symbol", "")
                # We display the symbol of the representative item (highest volume)
                # But maybe display normalized name in Name col?
                name = item.get("name", "")
                norm_name = normalize_name(name)

                display_name = norm_name[:20]

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

                print(f"{label:<15} | {symbol:<20} | {display_name:<20} | {fmt_close:<10} | {fmt_change:<8} | {fmt_rec:<5} | {fmt_adx:<6} | {fmt_vol:<6}")


if __name__ == "__main__":
    main()
