import json
import sys
from pathlib import Path


def load_json(filepath):
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        return None


def get_market_from_filename(filename, file_index):
    # Mapping based on the order in run_local_scans.sh
    # 1. Futures (14:14:51)
    # 2. CFD (14:14:52)
    # 3. Forex (14:15:00)
    # 4. ETF (14:15:02)
    # 5. Stocks (14:15:05)
    # Since timestamps might vary slightly, we rely on the order or content if possible.
    # But for this summary, mapping by sorted filename (timestamp) usually works if run sequentially.

    markets = ["Futures", "CFD", "Forex", "US ETFs", "US Stocks"]
    if 0 <= file_index < len(markets):
        return markets[file_index]
    return "Unknown"


def main():
    export_dir = Path("export")
    files = sorted(list(export_dir.glob("*.json")))

    if not files:
        print("No result files found in export/")
        return

    all_opportunities = []

    print(f"{'Market':<10} | {'Symbol':<20} | {'Name':<20} | {'Close':<10} | {'Change%':<8} | {'Rec':<5} | {'ADX':<6} | {'Vol.D':<6}")
    print("-" * 105)

    for i, filepath in enumerate(files):
        data = load_json(filepath)
        if not data:
            continue

        market = get_market_from_filename(filepath.name, i)

        if isinstance(data, dict):
            items = data.get("data", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []

        # Filter for passed items (though the export usually contains filtered results, let's check 'passes.all' if present)
        # The previous output showed items have "passes": {"all": true...}

        filtered_items = [item for item in items if item.get("passes", {}).get("all", False)]

        for item in filtered_items:
            symbol = item.get("symbol", "")
            name = item.get("name", "")[:20]  # Truncate
            close = item.get("close", 0)
            change = item.get("change", 0)
            rec = item.get("Recommend.All", 0)
            adx = item.get("ADX", 0)
            vol = item.get("Volatility.D", 0)

            # Format
            fmt_close = f"{close:.2f}"
            fmt_change = f"{change:+.2f}%"
            fmt_rec = f"{rec:.2f}"
            fmt_adx = f"{adx:.1f}" if adx else "-"
            fmt_vol = f"{vol:.1f}%" if vol else "-"

            print(f"{market:<10} | {symbol:<20} | {name:<20} | {fmt_close:<10} | {fmt_change:<8} | {fmt_rec:<5} | {fmt_adx:<6} | {fmt_vol:<6}")


if __name__ == "__main__":
    main()
