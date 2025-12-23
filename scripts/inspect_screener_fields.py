import json

from tradingview_scraper.symbols.screener import Screener


def inspect_fields():
    screener = Screener()
    # Likely candidates for start date
    columns = ["name", "close", "Perf.Y", "Perf.YTD", "Perf.All", "change", "volume"]

    # Try one by one for risky fields? No, batch.

    print(f"Requesting columns: {columns}")

    filters = [{"left": "exchange", "operation": "equal", "right": "BINANCE"}, {"left": "name", "operation": "equal", "right": "BTCUSDT"}]

    try:
        result = screener.screen(market="crypto", filters=filters, columns=columns, limit=1)

        if result["status"] == "success" and result["data"]:
            item = result["data"][0]
            print(json.dumps(item, indent=2))
        else:
            print("Failed:", result)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    inspect_fields()
