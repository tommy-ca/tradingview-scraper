import json

from tradingview_scraper.symbols.screener import Screener


def inspect_fields():
    screener = Screener()
    # Likely candidates for start date
    columns = [
        "name",
        "close",
        "volume",
        "Value.Traded",
        "market_cap_calc",
        "market_cap_basic",
        "change",
        "ADX",
        "Recommend.All",
        "Volatility.D",
        "Volatility.W",
        "Volatility.M",
        "Perf.W",
        "Perf.1M",
        "Perf.3M",
        "volume_change",
        "type",
    ]

    # Try one by one for risky fields? No, batch.

    print(f"Requesting columns: {columns}")

    filters = [{"left": "exchange", "operation": "equal", "right": "BINANCE"}, {"left": "type", "operation": "equal", "right": "spot"}, {"left": "name", "operation": "nmatch", "right": ".P$"}]

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
