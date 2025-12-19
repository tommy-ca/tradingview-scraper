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


def normalize_name(name):
    """Normalize crypto asset name by removing .P suffix for perps."""
    # Handle dot suffixes (e.g., BTCUSDT.P -> BTCUSDT)
    if "." in name:
        name = name.split(".")[0]
    return name


def main():
    export_dir = Path("export")
    all_files = sorted(list(export_dir.glob("universe_selector_*.json")), reverse=True)

    if not all_files:
        print("No result files found in export/")
        return

    # Group files by market_direction key - keep only most recent
    grouped = {}
    for f in all_files:
        # Extract market type from filename
        market_key = None
        if "binance_spot_long" in f.name:
            market_key = "binance_spot_long"
        elif "binance_spot_short" in f.name:
            market_key = "binance_spot_short"
        elif "binance_perp_long" in f.name:
            market_key = "binance_perp_long"
        elif "binance_perp_short" in f.name:
            market_key = "binance_perp_short"
        elif "okx_spot_long" in f.name:
            market_key = "okx_spot_long"
        elif "okx_spot_short" in f.name:
            market_key = "okx_spot_short"
        elif "okx_perp_long" in f.name:
            market_key = "okx_perp_long"
        elif "okx_perp_short" in f.name:
            market_key = "okx_perp_short"
        elif "bybit_spot_long" in f.name:
            market_key = "bybit_spot_long"
        elif "bybit_spot_short" in f.name:
            market_key = "bybit_spot_short"
        elif "bybit_perp_long" in f.name:
            market_key = "bybit_perp_long"
        elif "bybit_perp_short" in f.name:
            market_key = "bybit_perp_short"
        elif "bitget_spot_long" in f.name:
            market_key = "bitget_spot_long"
        elif "bitget_spot_short" in f.name:
            market_key = "bitget_spot_short"
        elif "bitget_perp_long" in f.name:
            market_key = "bitget_perp_long"
        elif "bitget_perp_short" in f.name:
            market_key = "bitget_perp_short"
        elif "crypto_spot_long" in f.name:
            market_key = "crypto_spot_long"
        elif "crypto_spot_short" in f.name:
            market_key = "crypto_spot_short"
        elif "crypto_perp_long" in f.name:
            market_key = "crypto_perp_long"
        elif "crypto_perp_short" in f.name:
            market_key = "crypto_perp_short"

        if not market_key:
            continue

        # Store only most recent file for each market_direction
        if market_key not in grouped:
            grouped[market_key] = f

    # Process order with proper labels (exchange, type, direction)
    order_map = [
        ("binance_spot_long", ("Binance", "Spot", "L")),
        ("binance_spot_short", ("Binance", "Spot", "S")),
        ("binance_perp_long", ("Binance", "Perp", "L")),
        ("binance_perp_short", ("Binance", "Perp", "S")),
        ("okx_spot_long", ("OKX", "Spot", "L")),
        ("okx_spot_short", ("OKX", "Spot", "S")),
        ("okx_perp_long", ("OKX", "Perp", "L")),
        ("okx_perp_short", ("OKX", "Perp", "S")),
        ("bybit_spot_long", ("Bybit", "Spot", "L")),
        ("bybit_spot_short", ("Bybit", "Spot", "S")),
        ("bybit_perp_long", ("Bybit", "Perp", "L")),
        ("bybit_perp_short", ("Bybit", "Perp", "S")),
        ("bitget_spot_long", ("Bitget", "Spot", "L")),
        ("bitget_spot_short", ("Bitget", "Spot", "S")),
        ("bitget_perp_long", ("Bitget", "Perp", "L")),
        ("bitget_perp_short", ("Bitget", "Perp", "S")),
        ("crypto_spot_long", ("All", "Spot", "L")),
        ("crypto_spot_short", ("All", "Spot", "S")),
        ("crypto_perp_long", ("All", "Perp", "L")),
        ("crypto_perp_short", ("All", "Perp", "S")),
    ]

    print(f"{'Exchange':<10} | {'Type':<4} | {'Dir':<3} | {'Symbol':<20} | {'Name':<20} | {'Close':<10} | {'Change%':<8} | {'Rec':<5} | {'ADX':<6} | {'Vol.D':<6}")
    print("-" * 118)

    for key, (exchange, market_type, direction) in order_map:
        if key not in grouped:
            continue

        filepath = grouped[key]
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
            vol_current = item.get("volume") or 0
            if norm_name in aggregated:
                vol_existing = aggregated[norm_name].get("volume") or 0
                if vol_current > vol_existing:
                    aggregated[norm_name] = item
            else:
                aggregated[norm_name] = item

        # Sort by Value.Traded desc
        sorted_items = sorted(aggregated.values(), key=lambda x: x.get("Value.Traded") or 0, reverse=True)

        for item in sorted_items:
            symbol = item.get("symbol", "")
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

            print(f"{exchange:<10} | {market_type:<4} | {direction:<3} | {symbol:<20} | {display_name:<20} | {fmt_close:<10} | {fmt_change:<8} | {fmt_rec:<5} | {fmt_adx:<6} | {fmt_vol:<6}")


if __name__ == "__main__":
    main()
